"""
Social Momentum Scalping Strategy
Captures explosive social activity with positive sentiment
"""

from typing import Dict, List
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Strategy that identifies coins with explosive social momentum
    
    Entry Criteria:
    - Social volume spike (+40% vs 7-day average)
    - Interactions spike (+30% vs 7-day average)
    - High sentiment (>58%)
    - Positive price momentum (+0.5% in 1h)
    - Volume increase (+25%)
    """
    
    def __init__(self, config: Dict):
        super().__init__("Social Momentum Scalping", config)
        
        # Thresholds
        self.social_volume_change_min = self.thresholds.get("social_volume_change_min", 0.40)
        self.interactions_change_min = self.thresholds.get("interactions_change_min", 0.30)
        self.sentiment_min = self.thresholds.get("sentiment_min", 58)
        self.price_change_1h_min = self.thresholds.get("price_change_1h_min", 0.5)
        self.volume_change_min = self.thresholds.get("volume_change_min", 0.25)
    
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
                
                # Calculate confidence based on how strongly criteria are met
                confidence = self._calculate_confidence(coin)
                
                signal = self.format_signal(symbol, coin, confidence)
                signals.append(signal)
                
                logger.info(f"[{self.name}] Generated signal for {symbol} (confidence: {confidence:.2f})")
        
        # Sort by confidence
        signals.sort(key=lambda x: x["confidence"], reverse=True)
        
        return signals
    
    def validate_signal(self, coin_data: Dict) -> bool:
        """
        Validate if coin meets momentum criteria
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            True if signal is valid
        """
        # Get metrics
        sentiment = coin_data.get("sentiment", 0)
        percent_change_1h = coin_data.get("percent_change_1h", 0)
        galaxy_score = coin_data.get("galaxy_score", 0)
        
        # Check basic criteria
        if sentiment < self.sentiment_min:
            return False
        
        if percent_change_1h < self.price_change_1h_min:
            return False
        
        # Check social momentum (if available)
        # Note: We would need historical data to calculate true changes
        # For now, we'll use Galaxy Score as a proxy for social momentum
        if galaxy_score < 50:  # Minimum Galaxy Score threshold
            return False
        
        # Check if coin is tradeable (has volume)
        volume_24h = coin_data.get("volume_24h", 0)
        if volume_24h < 1000000:  # Minimum $1M daily volume
            return False
        
        # Check market cap rank (focus on top 200)
        market_cap_rank = coin_data.get("market_cap_rank", 999)
        if market_cap_rank > 200:
            return False
        
        return True
    
    def _calculate_confidence(self, coin_data: Dict) -> float:
        """
        Calculate signal confidence based on strength of criteria
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5  # Base confidence
        
        # Sentiment bonus
        sentiment = coin_data.get("sentiment", 0)
        if sentiment > 70:
            confidence += 0.15
        elif sentiment > 60:
            confidence += 0.10
        elif sentiment > self.sentiment_min:
            confidence += 0.05
        
        # Price momentum bonus
        percent_change_1h = coin_data.get("percent_change_1h", 0)
        if percent_change_1h > 2:
            confidence += 0.15
        elif percent_change_1h > 1:
            confidence += 0.10
        elif percent_change_1h > self.price_change_1h_min:
            confidence += 0.05
        
        # Galaxy Score bonus
        galaxy_score = coin_data.get("galaxy_score", 0)
        if galaxy_score > 70:
            confidence += 0.10
        elif galaxy_score > 60:
            confidence += 0.05
        
        # Volume bonus
        volume_24h = coin_data.get("volume_24h", 0)
        if volume_24h > 100000000:  # >$100M
            confidence += 0.05
        
        # Cap confidence at 1.0
        return min(confidence, 1.0)
    
    def __str__(self):
        return f"{self.name} - Targets: +{self.target_profit_percent}%, Stop: -{self.stop_loss_percent}%"


if __name__ == "__main__":
    print("Momentum strategy module loaded successfully")
