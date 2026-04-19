"""
AltRank Breakout Hunter Strategy
Identifies coins with dramatic AltRank improvements
"""

from typing import Dict, List
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class AltRankStrategy(BaseStrategy):
    """
    Strategy that identifies coins improving rapidly in AltRank
    
    Entry Criteria:
    - AltRank improved by 15+ positions
    - Current AltRank < 120
    - Social dominance increased (+50%)
    - High sentiment (>60%)
    - Positive price momentum (+3% in 24h)
    - Not in top 20 (more volatility potential)
    """
    
    def __init__(self, config: Dict):
        super().__init__("AltRank Breakout Hunter", config)
        
        # Thresholds
        self.altrank_improvement_min = self.thresholds.get("altrank_improvement_min", 15)
        self.altrank_max = self.thresholds.get("altrank_max", 120)
        self.social_dominance_change_min = self.thresholds.get("social_dominance_change_min", 0.50)
        self.sentiment_min = self.thresholds.get("sentiment_min", 60)
        self.price_change_24h_min = self.thresholds.get("price_change_24h_min", 3)
        self.market_cap_rank_min = self.thresholds.get("market_cap_rank_min", 20)
    
    def generate_signals(self, market_data: List[Dict]) -> List[Dict]:
        """
        Generate signals from market data
        
        Args:
            market_data: List of enriched coin data
            
        Returns:
            List of trading signals
        """
        signals = []
        
        for coin in market_data:
            if self.validate_signal(coin):
                symbol = coin.get("symbol")
                
                # Calculate confidence
                confidence = self._calculate_confidence(coin)
                
                signal = self.format_signal(symbol, coin, confidence)
                signals.append(signal)
                
                altrank = coin.get("alt_rank")
                altrank_improvement = coin.get("altrank_improvement", 0)
                logger.info(f"[{self.name}] Generated signal for {symbol} (AltRank: {altrank}, Improved: +{altrank_improvement})")
        
        # Sort by AltRank improvement
        signals.sort(key=lambda x: x["metrics"].get("altrank_improvement", 0), reverse=True)
        
        return signals
    
    def validate_signal(self, coin_data: Dict) -> bool:
        """
        Validate if coin meets AltRank breakout criteria
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            True if signal is valid
        """
        # Get metrics
        alt_rank = coin_data.get("alt_rank")
        alt_rank_prev = coin_data.get("alt_rank_previous")
        altrank_improvement = coin_data.get("altrank_improvement", 0)
        sentiment = coin_data.get("sentiment", 0)
        percent_change_24h = coin_data.get("percent_change_24h", 0)
        market_cap_rank = coin_data.get("market_cap_rank", 999)
        
        # Check if we have AltRank data
        if alt_rank is None or alt_rank_prev is None:
            return False
        
        # Check AltRank improvement (lower is better, so improvement = prev - current)
        if altrank_improvement < self.altrank_improvement_min:
            return False
        
        # Check current AltRank is good enough
        if alt_rank > self.altrank_max:
            return False
        
        # Check sentiment
        if sentiment < self.sentiment_min:
            return False
        
        # Check price momentum
        if percent_change_24h < self.price_change_24h_min:
            return False
        
        # Prefer coins outside top 20 (more upside potential)
        if market_cap_rank <= self.market_cap_rank_min:
            return False
        
        # Check volume
        volume_24h = coin_data.get("volume_24h", 0)
        if volume_24h < 500000:  # Minimum $500K daily volume
            return False
        
        return True
    
    def _calculate_confidence(self, coin_data: Dict) -> float:
        """
        Calculate signal confidence
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5  # Base confidence
        
        # AltRank improvement bonus
        altrank_improvement = coin_data.get("altrank_improvement", 0)
        if altrank_improvement > 30:
            confidence += 0.20
        elif altrank_improvement > 20:
            confidence += 0.15
        elif altrank_improvement > self.altrank_improvement_min:
            confidence += 0.10
        
        # Current AltRank bonus (lower is better)
        alt_rank = coin_data.get("alt_rank", 999)
        if alt_rank < 50:
            confidence += 0.15
        elif alt_rank < 80:
            confidence += 0.10
        elif alt_rank < self.altrank_max:
            confidence += 0.05
        
        # Sentiment bonus
        sentiment = coin_data.get("sentiment", 0)
        if sentiment > 75:
            confidence += 0.10
        elif sentiment > 65:
            confidence += 0.05
        
        # Price momentum bonus
        percent_change_24h = coin_data.get("percent_change_24h", 0)
        if percent_change_24h > 8:
            confidence += 0.10
        elif percent_change_24h > 5:
            confidence += 0.05
        
        # Social dominance bonus
        social_dominance = coin_data.get("social_dominance", 0)
        if social_dominance > 1.0:  # >1% of total social volume
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def format_signal(self, symbol: str, coin_data: Dict, confidence: float = 0.8) -> Dict:
        """Override to include AltRank metrics"""
        signal = super().format_signal(symbol, coin_data, confidence)
        signal["metrics"]["altrank_improvement"] = coin_data.get("altrank_improvement", 0)
        signal["metrics"]["alt_rank_previous"] = coin_data.get("alt_rank_previous")
        signal["metrics"]["social_dominance"] = coin_data.get("social_dominance")
        return signal
    
    def __str__(self):
        return f"{self.name} - Targets: +{self.target_profit_percent}%, Stop: -{self.stop_loss_percent}%"


if __name__ == "__main__":
    print("AltRank strategy module loaded successfully")
