"""
Risk Management Module
Handles position sizing, risk limits, and circuit breakers
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages trading risk and position limits"""
    
    def __init__(self, config: Dict):
        """
        Initialize risk manager
        
        Args:
            config: Risk management configuration
        """
        self.initial_capital = float(config.get("initial_capital", 1000))
        self.max_positions = int(config.get("max_positions", 3))
        self.max_capital_in_use_percent = float(config.get("max_capital_in_use_percent", 80))
        self.reserve_percent = float(config.get("reserve_percent", 10))
        self.daily_loss_limit_percent = float(config.get("daily_loss_limit_percent", 8))
        self.total_loss_limit_percent = float(config.get("total_loss_limit_percent", 20))
        self.profit_lock_threshold_percent = float(config.get("profit_lock_threshold_percent", 15))
        
        # State tracking
        self.daily_pnl = 0
        self.daily_start_time = datetime.now()
        self.circuit_breaker_active = False
        self.locked_profits = 0
        self.active_positions: Dict[str, float] = {}  # symbol -> position_value_usd
        
        logger.info(f"Risk Manager initialized - Max positions: {self.max_positions}, Daily loss limit: {self.daily_loss_limit_percent}%")
    
    def add_position(self, symbol: str, position_value_usd: float):
        """
        Track a new position
        
        Args:
            symbol: Asset symbol
            position_value_usd: Position value in USD
        """
        self.active_positions[symbol] = self.active_positions.get(symbol, 0) + position_value_usd
        logger.info(f"Position tracked: {symbol} = ${self.active_positions[symbol]:.2f}")
    
    def remove_position(self, symbol: str):
        """
        Remove a tracked position
        
        Args:
            symbol: Asset symbol
        """
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            logger.info(f"Position removed: {symbol}")
    
    def get_total_exposure(self) -> float:
        """Get total capital currently in use"""
        return sum(self.active_positions.values())
    
    def can_open_position(self, current_positions: int, account_value: float) -> bool:
        """
        Check if a new position can be opened
        
        Args:
            current_positions: Number of currently open positions
            account_value: Current account value
            
        Returns:
            True if position can be opened
        """
        # Ensure inputs are numbers
        try:
            c_pos = int(current_positions) if current_positions is not None else 0
            acc_val = float(account_value) if account_value is not None else 0.0
            initial_cap = float(self.initial_capital)
            d_pnl = float(self.daily_pnl)
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid numeric input in can_open_position: {e}")
            return False

        # Check circuit breaker
        if self.circuit_breaker_active:
            logger.warning("Circuit breaker active - no new positions allowed")
            return False
        
        # Check max positions
        try:
            max_p = int(self.max_positions)
            current_p = int(c_pos)
            if current_p >= max_p:
                logger.debug(f"Max positions reached ({current_p}/{max_p})")
                return False
        except (TypeError, ValueError):
            # Fallback if max_positions is somehow not an int
            if int(c_pos) >= 3:
                return False
        
        # Check daily loss limit
        try:
            loss_limit = float(self.daily_loss_limit_percent)
            daily_loss_percent = (d_pnl / initial_cap) * 100
            if daily_loss_percent <= -loss_limit:
                logger.warning(f"Daily loss limit reached: {daily_loss_percent:.2f}%")
                self.activate_circuit_breaker("daily_loss_limit")
                return False
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.error(f"Error calculating daily loss limit: {e}")
            return False
        
        # Check total loss limit
        try:
            total_loss_limit = float(self.total_loss_limit_percent)
            total_pnl_percent = ((acc_val - initial_cap) / initial_cap) * 100
            if total_pnl_percent <= -total_loss_limit:
                logger.error(f"Total loss limit reached: {total_pnl_percent:.2f}%")
                self.activate_circuit_breaker("total_loss_limit")
                return False
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.error(f"Error calculating total loss limit: {e}")
            return False
        
        return True
    
    def calculate_position_size(self, strategy_config: Dict, available_capital: float,
                               entry_price: float, current_positions: int) -> float:
        """
        Calculate safe position size
        
        Args:
            strategy_config: Strategy configuration
            available_capital: Available capital
            entry_price: Entry price
            current_positions: Number of current positions
            
        Returns:
            Position size in units
        """
        # Get strategy parameters
        capital_percent = strategy_config.get("capital_percent", 33)
        leverage = strategy_config.get("leverage", 3)
        
        # Calculate base allocation
        strategy_capital = available_capital * (capital_percent / 100)
        
        # Apply position scaling based on current positions
        # Reduce size if we already have positions open
        position_scale = 1.0 - (current_positions * 0.15)  # 15% reduction per position
        position_scale = max(position_scale, 0.5)  # Minimum 50% of normal size
        
        strategy_capital *= position_scale
        
        # Calculate position value with leverage
        position_value = strategy_capital * leverage
        
        # Ensure we don't exceed max capital in use
        max_capital_in_use = available_capital * (self.max_capital_in_use_percent / 100)
        if position_value > max_capital_in_use:
            position_value = max_capital_in_use
            logger.warning(f"Position size capped at max capital in use: ${position_value:.2f}")
        
        # Ensure minimum order value for Hyperliquid ($10 minimum, use $15 for margin)
        MIN_ORDER_VALUE = 15.0
        if position_value < MIN_ORDER_VALUE:
            position_value = MIN_ORDER_VALUE
            logger.info(f"Position size increased to minimum: ${position_value:.2f}")
        
        # Calculate size in units
        size = position_value / entry_price
        
        logger.info(f"Calculated position size: {size:.4f} units (${position_value:.2f} value, {leverage}x leverage)")
        return size
    
    def validate_trade(self, trade_data: Dict, account_value: float) -> tuple[bool, str]:
        """
        Validate if a trade should be executed
        
        Args:
            trade_data: Trade data dictionary
            account_value: Current account value
            
        Returns:
            Tuple of (is_valid, reason)
        """
        symbol = trade_data.get("symbol")
        size = trade_data.get("size")
        entry_price = trade_data.get("entry_price")
        leverage = trade_data.get("leverage", 1)
        
        # Calculate position value
        position_value = size * entry_price
        
        # Check if position value is reasonable
        if position_value < 10:
            return False, f"Position value too small: ${position_value:.2f}"
        
        # Check if position value doesn't exceed account
        max_position_value = account_value * (self.max_capital_in_use_percent / 100)
        if position_value > max_position_value:
            return False, f"Position value ${position_value:.2f} exceeds max ${max_position_value:.2f}"
        
        # Check leverage is reasonable
        if leverage > 10:
            return False, f"Leverage {leverage}x too high"
        
        # All checks passed
        return True, "Trade validated"
    
    def update_daily_pnl(self, pnl: float):
        """
        Update daily PnL tracking
        
        Args:
            pnl: PnL from closed trade
        """
        # Check if we need to reset daily tracking
        if datetime.now() - self.daily_start_time > timedelta(days=1):
            logger.info(f"Daily reset - Previous day PnL: ${self.daily_pnl:.2f}")
            self.daily_pnl = 0
            self.daily_start_time = datetime.now()
        
        self.daily_pnl += pnl
        logger.info(f"Daily PnL updated: ${self.daily_pnl:.2f}")
    
    def check_profit_lock(self, account_value: float) -> bool:
        """
        Check if profits should be locked
        
        Args:
            account_value: Current account value
            
        Returns:
            True if profit lock should be activated
        """
        total_pnl_percent = ((account_value - self.initial_capital) / self.initial_capital) * 100
        
        if total_pnl_percent >= self.profit_lock_threshold_percent:
            if self.locked_profits == 0:
                # First time hitting threshold - lock current profits
                self.locked_profits = account_value - self.initial_capital
                logger.info(f"Profit lock activated at +{total_pnl_percent:.1f}% - Locked ${self.locked_profits:.2f}")
                return True
        
        return False
    
    def get_adjusted_stop_loss(self, entry_price: float, stop_loss: float, 
                               account_value: float, is_long: bool = True) -> float:
        """
        Get adjusted stop loss if profit lock is active
        
        Args:
            entry_price: Entry price
            stop_loss: Original stop loss
            account_value: Current account value
            is_long: True for long position
            
        Returns:
            Adjusted stop loss price
        """
        if self.locked_profits > 0:
            # Calculate break-even or small profit stop
            total_pnl_percent = ((account_value - self.initial_capital) / self.initial_capital) * 100
            
            if total_pnl_percent >= self.profit_lock_threshold_percent * 1.5:
                # Move stop to break-even + 2%
                if is_long:
                    adjusted_stop = entry_price * 1.02
                else:
                    adjusted_stop = entry_price * 0.98
                
                # Use the better stop (closer to current price)
                if is_long:
                    return max(stop_loss, adjusted_stop)
                else:
                    return min(stop_loss, adjusted_stop)
        
        return stop_loss
    
    def activate_circuit_breaker(self, reason: str):
        """
        Activate circuit breaker to stop all trading
        
        Args:
            reason: Reason for activation
        """
        self.circuit_breaker_active = True
        logger.error(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")
    
    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker"""
        self.circuit_breaker_active = False
        logger.info("Circuit breaker deactivated")
    
    def get_risk_status(self, account_value: float, open_positions: int) -> Dict:
        """
        Get current risk status
        
        Args:
            account_value: Current account value
            open_positions: Number of open positions
            
        Returns:
            Risk status dictionary
        """
        total_pnl = account_value - self.initial_capital
        total_pnl_percent = (total_pnl / self.initial_capital) * 100
        daily_pnl_percent = (self.daily_pnl / self.initial_capital) * 100
        
        # Calculate risk level
        if self.circuit_breaker_active:
            risk_level = "CRITICAL"
        elif abs(daily_pnl_percent) > self.daily_loss_limit_percent * 0.7:
            risk_level = "HIGH"
        elif open_positions >= self.max_positions:
            risk_level = "ELEVATED"
        else:
            risk_level = "NORMAL"
        
        return {
            "risk_level": risk_level,
            "circuit_breaker_active": self.circuit_breaker_active,
            "open_positions": open_positions,
            "max_positions": self.max_positions,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_percent": daily_pnl_percent,
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "locked_profits": self.locked_profits,
            "can_trade": not self.circuit_breaker_active and open_positions < self.max_positions
        }


if __name__ == "__main__":
    # Test the risk manager
    logging.basicConfig(level=logging.INFO)
    
    config = {
        "initial_capital": 1000,
        "max_positions": 3,
        "daily_loss_limit_percent": 8
    }
    
    rm = RiskManager(config)
    print(f"Can open position: {rm.can_open_position(0, 1000)}")
    print(f"Risk status: {rm.get_risk_status(1000, 0)}")
    print("Risk manager module loaded successfully")
