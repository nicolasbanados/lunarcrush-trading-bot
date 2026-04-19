"""
Galaxy Score Reversal Strategy
Buys dips when social fundamentals remain strong
"""

from typing import Dict, List
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class ReversalStrategy(BaseStrategy):
    """
    Strategy that identifies buying opportunities in price dips
    with strong social fundamentals
    
    Entry Criteria:
    - Price dropped -5% or more in 24h
    - Galaxy Score remains high (>70)
    - Sentiment still positive (>60%)
    - Social volume increasing (+30%)
    - Divergence: Price down but social metrics up
    """
    
    def __init__(self, config: Dict):
        super().__init__("Galaxy Score Reversal", config)
        
        # Thresholds
        self.price_change_24h_max = self.thresholds.get("price_change_24h_max", -5)
        self.galaxy_score_min = self.thresholds.get("galaxy_score_min", 70)
        self.sentiment_min = self.thresholds.get("sentiment_min", 60)
        self.social_volume_change_min = self.thresholds.get("social_volume_change_min", 0.30)
    
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
            if not isinstance(coin, dict):
                continue
            if self.validate_signal(coin):
                symbol = coin.get("symbol")
                
                # Calculate confidence
                confidence = self._calculate_confidence(coin)
                
                signal = self.format_signal(symbol, coin, confidence)
                signals.append(signal)
                
                price_change = coin.get("percent_change_24h", 0)
                galaxy_score = coin.get("galaxy_score", 0)
                logger.info(f"[{self.name}] Generated signal for {symbol} (Price: {price_change:.1f}%, Galaxy: {galaxy_score})")
        
        # Sort by Galaxy Score (higher is better for reversals)
        signals.sort(key=lambda x: x["metrics"].get("galaxy_score", 0), reverse=True)
        
        return signals
    
    def validate_signal(self, coin_data: Dict) -> bool:
        """
        Validate if coin meets reversal criteria
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            True if signal is valid
        """
        # Get metrics
        percent_change_24h = coin_data.get("percent_change_24h", 0)
        galaxy_score = coin_data.get("galaxy_score", 0)
        galaxy_score_prev = coin_data.get("galaxy_score_previous", 0)
        sentiment = coin_data.get("sentiment", 0)
        
        # Check if price dropped significantly
        if percent_change_24h > self.price_change_24h_max:
            return False
        
        # Check if Galaxy Score is still strong
        if galaxy_score < self.galaxy_score_min:
            return False
        
        # Check if Galaxy Score is stable or improving (divergence signal)
        if galaxy_score_prev > 0 and galaxy_score < galaxy_score_prev:
            return False
        
        # Check sentiment remains positive
        if sentiment < self.sentiment_min:
            return False
        
        # Check volume (need liquidity for reversal)
        volume_24h = coin_data.get("volume_24h", 0)
        if volume_24h < 2000000:  # Minimum $2M daily volume
            return False
        
        # Focus on established coins (top 100)
        market_cap_rank = coin_data.get("market_cap_rank", 999)
        if market_cap_rank > 100:
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
        
        # Price drop bonus (bigger drop = better entry, but cap at -15%)
        percent_change_24h = coin_data.get("percent_change_24h", 0)
        price_drop = abs(percent_change_24h)
        if price_drop > 10:
            confidence += 0.20
        elif price_drop > 7:
            confidence += 0.15
        elif price_drop > 5:
            confidence += 0.10
        
        # Galaxy Score bonus
        galaxy_score = coin_data.get("galaxy_score", 0)
        if galaxy_score > 80:
            confidence += 0.15
        elif galaxy_score > 75:
            confidence += 0.10
        elif galaxy_score > self.galaxy_score_min:
            confidence += 0.05
        
        # Galaxy Score momentum bonus (increasing despite price drop)
        galaxy_score_change = coin_data.get("galaxy_score_change", 0)
        if galaxy_score_change > 5:
            confidence += 0.15
        elif galaxy_score_change > 0:
            confidence += 0.10
        
        # Sentiment bonus
        sentiment = coin_data.get("sentiment", 0)
        if sentiment > 70:
            confidence += 0.10
        elif sentiment > 65:
            confidence += 0.05
        
        # Social dominance bonus (strong community support)
        social_dominance = coin_data.get("social_dominance", 0)
        if social_dominance > 2.0:  # >2% of total social volume
            confidence += 0.10
        elif social_dominance > 1.0:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def format_signal(self, symbol: str, coin_data: Dict, confidence: float = 0.8) -> Dict:
        """Override to include reversal-specific metrics"""
        signal = super().format_signal(symbol, coin_data, confidence)
        signal["metrics"]["galaxy_score_change"] = coin_data.get("galaxy_score_change", 0)
        signal["metrics"]["galaxy_score_previous"] = coin_data.get("galaxy_score_previous")
        signal["metrics"]["social_dominance"] = coin_data.get("social_dominance")
        return signal
    
    def __str__(self):
        return f"{self.name} - Targets: +{self.target_profit_percent}%, Stop: -{self.stop_loss_percent}%"


if __name__ == "__main__":
    print("Reversal strategy module loaded successfully")
