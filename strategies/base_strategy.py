"""
Base Strategy Class
Abstract base class for all trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""
    
    def __init__(self, name: str, config: Dict):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            config: Strategy configuration dictionary
        """
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)
        self.capital_percent = config.get("capital_percent", 33)
        self.leverage = config.get("leverage", 3)
        self.max_positions = config.get("max_positions", 1)
        self.target_profit_percent = config.get("target_profit_percent", 10)
        self.stop_loss_percent = config.get("stop_loss_percent", 3)
        self.trailing_stop_trigger_percent = config.get("trailing_stop_trigger_percent", 5)
        self.trailing_stop_percent = config.get("trailing_stop_percent", 2)
        self.time_stop_hours = config.get("time_stop_hours", 12)
        self.thresholds = config.get("thresholds", {})
        
        logger.info(f"Initialized strategy: {name}")
    
    @abstractmethod
    def generate_signals(self, market_data: List[Dict]) -> List[Dict]:
        """
        Generate trading signals from market data
        
        Args:
            market_data: List of coin data with social metrics
            
        Returns:
            List of signal dictionaries
        """
        pass
    
    @abstractmethod
    def validate_signal(self, coin_data: Dict) -> bool:
        """
        Validate if a coin meets strategy criteria
        
        Args:
            coin_data: Coin data dictionary
            
        Returns:
            True if signal is valid
        """
        pass
    
    def calculate_position_size(self, available_capital: float, entry_price: float) -> float:
        """
        Calculate position size based on available capital and leverage
        
        Args:
            available_capital: Available capital in USD
            entry_price: Entry price per unit
            
        Returns:
            Position size in units
        """
        # Calculate capital allocation for this strategy
        strategy_capital = available_capital * (self.capital_percent / 100)
        
        # Calculate position value with leverage
        position_value = strategy_capital * self.leverage
        
        # Calculate size in units
        size = position_value / entry_price
        
        return size
    
    def calculate_stop_loss(self, entry_price: float, is_long: bool = True) -> float:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            is_long: True for long position, False for short
            
        Returns:
            Stop loss price
        """
        if is_long:
            return entry_price * (1 - self.stop_loss_percent / 100)
        else:
            return entry_price * (1 + self.stop_loss_percent / 100)
    
    def calculate_take_profit(self, entry_price: float, is_long: bool = True) -> float:
        """
        Calculate take profit price
        
        Args:
            entry_price: Entry price
            is_long: True for long position, False for short
            
        Returns:
            Take profit price
        """
        if is_long:
            return entry_price * (1 + self.target_profit_percent / 100)
        else:
            return entry_price * (1 - self.target_profit_percent / 100)
    
    def should_use_trailing_stop(self, entry_price: float, current_price: float, 
                                 is_long: bool = True) -> bool:
        """
        Check if trailing stop should be activated
        
        Args:
            entry_price: Entry price
            current_price: Current price
            is_long: True for long position
            
        Returns:
            True if trailing stop should be used
        """
        if is_long:
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        return profit_percent >= self.trailing_stop_trigger_percent
    
    def calculate_trailing_stop(self, current_price: float, is_long: bool = True) -> float:
        """
        Calculate trailing stop price
        
        Args:
            current_price: Current price
            is_long: True for long position
            
        Returns:
            Trailing stop price
        """
        if is_long:
            return current_price * (1 - self.trailing_stop_percent / 100)
        else:
            return current_price * (1 + self.trailing_stop_percent / 100)
    
    def format_signal(self, symbol: str, coin_data: Dict, confidence: float = 0.8) -> Dict:
        """
        Format a trading signal
        
        Args:
            symbol: Asset symbol
            coin_data: Coin data dictionary
            confidence: Signal confidence (0-1)
            
        Returns:
            Formatted signal dictionary
        """
        return {
            "timestamp": datetime.now().timestamp(),
            "strategy": self.name,
            "symbol": symbol,
            "signal_type": "buy",  # Default to buy (long only for now)
            "confidence": confidence,
            "leverage": self.leverage,
            "target_profit_percent": self.target_profit_percent,
            "stop_loss_percent": self.stop_loss_percent,
            "metrics": {
                "price": coin_data.get("price"),
                "galaxy_score": coin_data.get("galaxy_score"),
                "alt_rank": coin_data.get("alt_rank"),
                "sentiment": coin_data.get("sentiment"),
                "social_volume_24h": coin_data.get("social_volume_24h"),
                "interactions_24h": coin_data.get("interactions_24h"),
                "percent_change_24h": coin_data.get("percent_change_24h")
            }
        }
    
    def __str__(self):
        return f"{self.name} (Leverage: {self.leverage}x, Capital: {self.capital_percent}%)"


if __name__ == "__main__":
    print("Base strategy module loaded successfully")
