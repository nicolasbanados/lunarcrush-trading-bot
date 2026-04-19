"""
Position Manager Module
Manages open positions, stop losses, and take profits
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)


class Position:
    """Represents an open trading position"""
    
    def __init__(self, trade_id: int, symbol: str, strategy: str, entry_price: float,
                 size: float, leverage: int, stop_loss: float, take_profit: float,
                 entry_time: float):
        self.trade_id = trade_id
        self.symbol = symbol
        self.strategy = strategy
        self.entry_price = entry_price
        self.size = size
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.entry_time = entry_time
        self.trailing_stop = None
        self.highest_price = entry_price
        self.last_check_time = time.time()
        
    def update_trailing_stop(self, current_price: float, trailing_stop_percent: float):
        """Update trailing stop based on current price"""
        # Update highest price
        if current_price > self.highest_price:
            self.highest_price = current_price
        
        # Calculate trailing stop
        new_trailing_stop = self.highest_price * (1 - trailing_stop_percent / 100)
        
        # Only update if new stop is higher than current
        if self.trailing_stop is None or new_trailing_stop > self.trailing_stop:
            self.trailing_stop = new_trailing_stop
            logger.debug(f"{self.symbol} trailing stop updated to ${new_trailing_stop:.2f}")
    
    def get_current_pnl(self, current_price: float) -> tuple[float, float]:
        """
        Calculate current PnL
        
        Returns:
            Tuple of (pnl_usd, pnl_percent)
        """
        position_value = self.size * self.entry_price
        current_value = self.size * current_price
        pnl_usd = (current_value - position_value) * self.leverage
        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        
        return pnl_usd, pnl_percent
    
    def should_close(self, current_price: float, strategy_config: Dict) -> tuple[bool, str]:
        """
        Check if position should be closed
        
        Returns:
            Tuple of (should_close, reason)
        """
        # Check stop loss
        if current_price <= self.stop_loss:
            return True, "stop_loss"
        
        # Check trailing stop
        if self.trailing_stop and current_price <= self.trailing_stop:
            return True, "trailing_stop"
        
        # Check take profit
        if current_price >= self.take_profit:
            return True, "take_profit"
        
        # Check time stop
        if getattr(self, 'entry_time', None) is None:
            return False, ""
            
        time_stop_hours = strategy_config.get("time_stop_hours", 24)
        time_in_position = (time.time() - self.entry_time) / 3600  # Convert to hours
        if time_in_position >= time_stop_hours:
            return True, "time_stop"
        
        return False, ""
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary"""
        pnl_usd, pnl_percent = self.get_current_pnl(self.highest_price)
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "size": self.size,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop,
            "highest_price": self.highest_price,
            "entry_time": self.entry_time,
            "unrealized_pnl": pnl_usd,
            "unrealized_pnl_percent": pnl_percent
        }


class PositionManager:
    """Manages all open positions"""
    
    def __init__(self, hyperliquid_client, database, risk_manager):
        """
        Initialize position manager
        
        Args:
            hyperliquid_client: Hyperliquid client instance
            database: Database instance
            risk_manager: Risk manager instance
        """
        self.hl_client = hyperliquid_client
        self.db = database
        self.risk_manager = risk_manager
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        
        logger.info("Position Manager initialized")
    
    def add_position(self, symbol: str, side: str, size: float, entry_price: float,
                    leverage: int, strategy: str, stop_loss_percent: float = 5.0,
                    take_profit_percent: float = 10.0) -> bool:
        """
        Add a position that was already filled on the exchange
        
        Args:
            symbol: Asset symbol
            side: 'long' or 'short'
            size: Position size in coins
            entry_price: Fill price
            leverage: Leverage used
            strategy: Strategy name
            stop_loss_percent: Stop loss percentage
            take_profit_percent: Take profit percentage
            
        Returns:
            True if added successfully
        """
        if symbol in self.positions:
            # Update existing position (add to it)
            existing = self.positions[symbol]
            total_size = existing.size + size
            avg_price = (existing.entry_price * existing.size + entry_price * size) / total_size
            existing.size = total_size
            existing.entry_price = avg_price
            logger.info(f"Updated position {symbol}: size={total_size:.6f}, avg_price=${avg_price:.4f}")
            return True
        
        # Calculate stop loss and take profit based on side
        if side == 'long':
            stop_loss = entry_price * (1 - stop_loss_percent / 100)
            take_profit = entry_price * (1 + take_profit_percent / 100)
        else:
            stop_loss = entry_price * (1 + stop_loss_percent / 100)
            take_profit = entry_price * (1 - take_profit_percent / 100)
        
        # Create position object
        position = Position(
            trade_id=0,  # Will be updated when logged
            symbol=symbol,
            strategy=strategy,
            entry_price=entry_price,
            size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=time.time()
        )
        
        self.positions[symbol] = position
        logger.info(f"Added position: {symbol} {side} {size:.6f} @ ${entry_price:.4f}")
        return True
    
    def open_position(self, signal: Dict, strategy_config: Dict, 
                     available_capital: float) -> Optional[int]:
        """
        Open a new position based on signal
        
        Args:
            signal: Trading signal
            strategy_config: Strategy configuration
            available_capital: Available capital
            
        Returns:
            Trade ID or None if failed
        """
        symbol = signal["symbol"]
        
        # Check if we already have a position in this symbol
        if symbol in self.positions:
            logger.warning(f"Already have open position in {symbol}")
            return None
        
        # Check if we can open a new position
        if not self.risk_manager.can_open_position(len(self.positions), available_capital):
            logger.warning("Cannot open new position - risk limits")
            return None
        
        # Get current price
        mids = self.hl_client.get_all_mids()
        current_price = mids.get(symbol)
        
        if current_price is None:
            logger.error(f"No price available for {symbol}")
            return None
        
        # Calculate position size
        size = self.risk_manager.calculate_position_size(
            strategy_config,
            available_capital,
            current_price,
            len(self.positions)
        )
        
        # Calculate stop loss and take profit
        leverage = strategy_config["leverage"]
        stop_loss_percent = strategy_config["stop_loss_percent"]
        target_profit_percent = strategy_config["target_profit_percent"]
        
        stop_loss = current_price * (1 - stop_loss_percent / 100)
        take_profit = current_price * (1 + target_profit_percent / 100)
        
        # Validate trade
        trade_data = {
            "symbol": symbol,
            "size": size,
            "entry_price": current_price,
            "leverage": leverage
        }
        
        is_valid, reason = self.risk_manager.validate_trade(trade_data, available_capital)
        if not is_valid:
            logger.error(f"Trade validation failed: {reason}")
            return None
        
        # Set leverage on Hyperliquid
        logger.info(f"Setting leverage for {symbol}: {leverage}x")
        self.hl_client.update_leverage(symbol, leverage, is_cross=False)
        
        # Place market order
        logger.info(f"Opening position: {symbol} - Size: {size:.4f}, Price: ${current_price:.2f}")
        order_result = self.hl_client.place_market_order(symbol, True, size)
        
        if order_result.get("status") == "error":
            logger.error(f"Failed to place order: {order_result.get('error')}")
            return None
        
        # Log trade in database
        trade_id = self.db.log_trade({
            "timestamp": datetime.now().timestamp(),
            "symbol": symbol,
            "strategy": signal["strategy"],
            "side": "long",
            "entry_price": current_price,
            "size": size,
            "leverage": leverage,
            "status": "open",
            "entry_time": time.time(),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "signal_data": signal
        })
        
        # Create position object
        position = Position(
            trade_id=trade_id,
            symbol=symbol,
            strategy=signal["strategy"],
            entry_price=current_price,
            size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=time.time()
        )
        
        self.positions[symbol] = position
        
        logger.info(f"✅ Position opened: {symbol} #{trade_id} - Entry: ${current_price:.2f}, Stop: ${stop_loss:.2f}, Target: ${take_profit:.2f}")
        
        return trade_id
    
    def close_position(self, symbol: str, reason: str = "manual") -> bool:
        """
        Close an open position
        
        Args:
            symbol: Asset symbol
            reason: Reason for closing
            
        Returns:
            True if successful
        """
        if symbol not in self.positions:
            logger.warning(f"No open position for {symbol}")
            return False
        
        position = self.positions[symbol]
        
        # Get current price
        mids = self.hl_client.get_all_mids()
        current_price = mids.get(symbol)
        
        if current_price is None:
            logger.error(f"No price available for {symbol}")
            return False
        
        # Place closing order (sell)
        logger.info(f"Closing position: {symbol} at ${current_price:.2f}")
        order_result = self.hl_client.place_market_order(symbol, False, position.size, reduce_only=True)
        
        if order_result.get("status") == "error":
            logger.error(f"Failed to close position: {order_result.get('error')}")
            return False
        
        # Calculate PnL
        pnl_usd, pnl_percent = position.get_current_pnl(current_price)
        
        # Update database
        self.db.update_trade(position.trade_id, {
            "exit_price": current_price,
            "exit_time": time.time(),
            "pnl": pnl_usd,
            "pnl_percent": pnl_percent,
            "status": "closed",
            "exit_reason": reason
        })
        
        # Update risk manager
        self.risk_manager.update_daily_pnl(pnl_usd)
        
        # Remove position
        del self.positions[symbol]
        
        logger.info(f"✅ Position closed: {symbol} - PnL: ${pnl_usd:.2f} ({pnl_percent:+.2f}%) - Reason: {reason}")
        
        return True
    
    def monitor_positions(self, strategies_config: Dict):
        """
        Monitor all open positions and close if needed
        
        Args:
            strategies_config: Dictionary of strategy configurations
        """
        if not self.positions:
            return
        
        # Get current prices
        mids = self.hl_client.get_all_mids()
        
        positions_to_close = []
        
        for symbol, position in self.positions.items():
            current_price = mids.get(symbol)
            
            if current_price is None:
                logger.warning(f"No price for {symbol}, skipping")
                continue
            
            # Get strategy config
            strategy_name = position.strategy.lower().replace(" ", "_")
            if "momentum" in strategy_name:
                strategy_key = "momentum"
            elif "altrank" in strategy_name:
                strategy_key = "altrank"
            elif "reversal" in strategy_name:
                strategy_key = "reversal"
            else:
                strategy_key = "momentum"  # Default
            
            strategy_config = strategies_config.get(strategy_key, {})
            
            # Check if trailing stop should be activated
            trailing_trigger = strategy_config.get("trailing_stop_trigger_percent", 5)
            trailing_percent = strategy_config.get("trailing_stop_percent", 2)
            
            pnl_usd, pnl_percent = position.get_current_pnl(current_price)
            
            if pnl_percent >= trailing_trigger:
                position.update_trailing_stop(current_price, trailing_percent)
            
            # Check if position should be closed
            should_close, reason = position.should_close(current_price, strategy_config)
            
            if should_close:
                positions_to_close.append((symbol, reason))
                logger.info(f"Position {symbol} should close: {reason} (Price: ${current_price:.2f}, PnL: {pnl_percent:+.2f}%)")
        
        # Close positions
        for symbol, reason in positions_to_close:
            self.close_position(symbol, reason)
    
    def get_open_positions(self) -> List[Dict]:
        """Get list of open positions"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_position_count(self) -> int:
        """Get number of open positions"""
        return len(self.positions)
    
    def close_all_positions(self, reason: str = "shutdown"):
        """Close all open positions"""
        logger.info(f"Closing all {len(self.positions)} positions")
        
        for symbol in list(self.positions.keys()):
            self.close_position(symbol, reason)


if __name__ == "__main__":
    print("Position manager module loaded successfully")
