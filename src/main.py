import asyncio
import logging
import os
import sys
import time
import json
import requests
from datetime import datetime
from typing import List, Dict

from lunarcrush_client import LunarCrushClient
from hyperliquid_client import HyperliquidClient
from database import Database
from risk_manager import RiskManager
from position_manager import PositionManager
from strategies.momentum_strategy import MomentumStrategy
from strategies.altrank_strategy import AltRankStrategy
from strategies.reversal_strategy import ReversalStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MainBot")

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    if not os.path.exists(config_path):
        config_path = 'config/config.json'
    with open(config_path, 'r') as f:
        return json.load(f)

def get_bot_state():
    """Read bot state from state file (managed by API server)"""
    state_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'bot_state.json')
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {'status': 'running', 'pause_requested': False}

class TradingBot:
    def __init__(self):
        self.logger = logger
        self.is_running = False
        self.config = load_config()
        
        self.db = Database()
        api_key = os.environ.get('LUNARCRUSH_API_KEY', '')
        self.lc_client = LunarCrushClient(api_key)
        private_key = os.environ.get('HYPERLIQUID_PRIVATE_KEY', '')
        wallet_address = os.environ.get('HYPERLIQUID_WALLET_ADDRESS', '')
        self.hl_client = HyperliquidClient(private_key, wallet_address)
        self.risk_manager = RiskManager(self.config.get('trading', {}))
        self.position_manager = PositionManager(self.hl_client, self.db, self.risk_manager)
        
        strategy_configs = self.config.get('strategies', {})
        self.strategies = [
            MomentumStrategy(strategy_configs.get('momentum', {})),
            AltRankStrategy(strategy_configs.get('altrank', {})),
            ReversalStrategy(strategy_configs.get('reversal', {}))
        ]
        
        self.logger.info("Trading Bot initialized successfully")

    async def start(self):
        self.is_running = True
        self.logger.info("Starting trading bot loop...")
        
        await self.check_connection()
        
        while self.is_running:
            try:
                start_time = time.time()
                is_test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
                
                # Check if bot is paused (from dashboard control)
                bot_state = get_bot_state()
                is_paused = bot_state.get('paused', False)
                is_stopped = bot_state.get('status') == 'stopped'
                
                if is_stopped:
                    self.logger.info("Bot stopped via dashboard - exiting")
                    self.is_running = False
                    break
                
                # Sync positions with Hyperliquid (live mode only)
                if not is_test_mode:
                    await self.sync_positions_with_exchange()
                
                # If paused, only monitor positions but don't open new ones
                if is_paused:
                    self.logger.info("Bot paused - monitoring positions only, no new trades")
                    if not is_test_mode:
                        await self.monitor_positions()
                    await asyncio.sleep(30)  # Check more frequently when paused
                    continue
                
                coins = self.lc_client.get_enriched_coins_data(100)
                if coins:
                    self.logger.info(f"Fetched {len(coins)} coins from LunarCrush")
                    
                    # Get real account value for risk management
                    if is_test_mode:
                        account_value = float(self.risk_manager.initial_capital)
                    else:
                        try:
                            account_value = float(self.hl_client.get_account_value())
                        except Exception as e:
                            self.logger.error(f"Error fetching account value: {e}")
                            account_value = 0.0
                    
                    for strategy in self.strategies:
                        if not strategy.enabled:
                            continue
                            
                        self.logger.info(f"Running strategy: {strategy.name}")
                        signals = strategy.generate_signals(coins)
                        if signals is None:
                            signals = []
                        self.logger.info(f"Strategy {strategy.name} generated {len(signals)} signals")
                        
                        open_count_raw = self.position_manager.get_position_count()
                        try:
                            # Explicitly check if it's already an int or can be cast
                            if open_count_raw is None:
                                open_count = 0
                            else:
                                open_count = int(open_count_raw)
                        except (TypeError, ValueError):
                            open_count = 0
                                
                        max_pos = 3
                        try:
                            if hasattr(self.risk_manager, 'max_positions'):
                                val = self.risk_manager.max_positions
                                if val is not None:
                                    max_pos = int(val)
                        except (TypeError, ValueError):
                            max_pos = 3
                                    
                        available_slots = 0
                        try:
                            # Use max() to ensure available_slots is at least 0
                            available_slots = max(0, int(max_pos) - int(open_count))
                        except (TypeError, ValueError):
                            available_slots = 0

                        if available_slots > 0:
                            # Ensure signals is a list and slice safely
                            valid_signals = signals if isinstance(signals, list) else []
                            for signal in valid_signals[:available_slots]:
                                # Check risk before each trade
                                try:
                                    if not isinstance(signal, dict):
                                        continue
                                        
                                    sym = str(signal.get('symbol', ''))
                                    if not sym:
                                        continue
                                        
                                    # Safety check for account_value and open_count
                                    try:
                                        safe_open_count = int(open_count)
                                    except (TypeError, ValueError):
                                        safe_open_count = 0
                                        
                                    try:
                                        safe_account_value = float(account_value)
                                    except (TypeError, ValueError):
                                        safe_account_value = 0.0
                                    
                                    # Use a local variable for can_trade to avoid any comparison issues
                                    can_trade = self.risk_manager.can_open_position(safe_open_count, safe_account_value)
                                    
                                    if can_trade:
                                        await self.execute_trade(signal)
                                        open_count += 1
                                    else:
                                        self.logger.warning("Risk limits reached, skipping remaining signals")
                                        break
                                except Exception as e:
                                    self.logger.error(f"Error checking risk or executing trade: {e}")
                                    break
                
                # Monitor and close positions if needed (live mode)
                if not is_test_mode:
                    await self.monitor_positions()
                
                elapsed = time.time() - start_time
                sleep_time = max(180 - elapsed, 10)
                self.logger.info(f"Loop completed. Sleeping for {sleep_time:.2f}s")
                
                try:
                    requests.post('http://localhost:5000/api/update-scan', timeout=2)
                except:
                    pass
                
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(60)
    
    async def sync_positions_with_exchange(self):
        """Synchronize local position state with Hyperliquid exchange"""
        try:
            user_state = self.hl_client.get_user_state()
            if not user_state:
                self.logger.warning("Could not get user state from Hyperliquid")
                return
            
            exchange_positions = {}
            for pos in user_state.get("assetPositions", []):
                position = pos.get("position", {})
                size = float(position.get("szi", 0))
                if size != 0:
                    symbol = position.get("coin", "")
                    lev = position.get("leverage", {})
                    leverage = float(lev.get("value", 1)) if isinstance(lev, dict) else float(lev) if lev else 1
                    exchange_positions[symbol] = {
                        'size': size,
                        'entry_price': float(position.get("entryPx", 0)),
                        'unrealized_pnl': float(position.get("unrealizedPnl", 0)),
                        'leverage': leverage
                    }
            
            # Get database trades to match with exchange positions
            db_trades = self.db.get_all_trades()
            open_db_trades = {t['symbol']: t for t in db_trades if t.get('status') == 'OPEN'}
            
            # Sync exchange positions into position_manager
            # Clear local positions that don't exist on exchange
            local_symbols = list(self.position_manager.positions.keys())
            for symbol in local_symbols:
                if symbol not in exchange_positions:
                    self.logger.info(f"Position {symbol} closed on exchange, removing from tracker")
                    
                    # Update database trade as closed if we have a record
                    if symbol in open_db_trades:
                        trade = open_db_trades[symbol]
                        mids = self.hl_client.get_all_mids()
                        exit_price = mids.get(symbol, trade.get('entry_price', 0))
                        entry_price = trade.get('entry_price', exit_price)
                        
                        # Calculate PnL based on trade direction
                        trade_side = trade.get('side', 'long')
                        if trade_side == 'long':
                            pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
                        else:  # short
                            pnl_pct = ((entry_price - exit_price) / entry_price * 100) if entry_price else 0
                        
                        # PnL in USD = notional * pnl_pct (size is already in USD terms)
                        pnl_usd = trade.get('size', 0) * (pnl_pct / 100)
                        
                        self.db.update_trade(trade.get('id', trade.get('trade_id')), {
                            'exit_price': exit_price,
                            'exit_time': time.time(),
                            'pnl': pnl_usd,
                            'pnl_percent': pnl_pct,
                            'status': 'WIN' if pnl_usd > 0 else 'LOSS',
                            'exit_reason': 'exchange_sync'
                        })
                        self.risk_manager.update_daily_pnl(pnl_usd)
                        self.logger.info(f"Marked {symbol} ({trade_side}) as closed in database (synced from exchange)")
                    
                    if symbol in self.position_manager.positions:
                        del self.position_manager.positions[symbol]
            
            # Add exchange positions to local tracker if not already tracked
            strategy_configs = self.config.get('strategies', {})
            
            for symbol, pos_data in exchange_positions.items():
                if symbol not in self.position_manager.positions:
                    self.logger.info(f"Found untracked position {symbol} on exchange, adding to tracker")
                    
                    # Determine if long or short
                    is_long = pos_data['size'] > 0
                    expected_side = 'long' if is_long else 'short'
                    
                    # Try to match with database trade (by symbol AND side)
                    db_trade = None
                    for t in db_trades:
                        if t.get('status') == 'OPEN' and t.get('symbol') == symbol:
                            trade_side = t.get('side', 'long')
                            if trade_side == expected_side:
                                db_trade = t
                                break
                    
                    if db_trade:
                        # Use data from database trade
                        trade_id = db_trade.get('id', db_trade.get('trade_id', -1))
                        strategy_name = db_trade.get('strategy', 'Unknown')
                        
                        # Get strategy-specific config
                        strategy_key = 'momentum'  # default
                        if 'altrank' in strategy_name.lower():
                            strategy_key = 'altrank'
                        elif 'reversal' in strategy_name.lower():
                            strategy_key = 'reversal'
                        elif 'momentum' in strategy_name.lower():
                            strategy_key = 'momentum'
                        
                        strat_config = strategy_configs.get(strategy_key, {})
                        stop_loss_pct = strat_config.get('stop_loss_percent', 3.0)
                        take_profit_pct = strat_config.get('target_profit_percent', 8.0)
                        leverage = db_trade.get('leverage', int(pos_data['leverage']))
                    else:
                        # Use defaults for truly unknown positions
                        trade_id = -1
                        strategy_name = "Unknown (from exchange)"
                        stop_loss_pct = 3.0
                        take_profit_pct = 8.0
                        leverage = int(pos_data['leverage'])
                    
                    # Calculate stop and target prices (different for long vs short)
                    entry_price = pos_data['entry_price']
                    if is_long:
                        stop_loss = entry_price * (1 - stop_loss_pct / 100)
                        take_profit = entry_price * (1 + take_profit_pct / 100)
                    else:
                        # For shorts: stop loss is ABOVE entry, take profit is BELOW
                        stop_loss = entry_price * (1 + stop_loss_pct / 100)
                        take_profit = entry_price * (1 - take_profit_pct / 100)
                    
                    # Create Position object
                    from position_manager import Position
                    position = Position(
                        trade_id=trade_id,
                        symbol=symbol,
                        strategy=strategy_name,
                        entry_price=entry_price,
                        size=abs(pos_data['size']),
                        leverage=leverage,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        entry_time=time.time()
                    )
                    # Store side information for PnL calculations
                    position.is_long = is_long
                    self.position_manager.positions[symbol] = position
            
            # Log current exchange state
            position_count = len(exchange_positions)
            if exchange_positions:
                self.logger.info(f"Exchange positions ({position_count}): {list(exchange_positions.keys())}")
                for symbol, pos in exchange_positions.items():
                    pnl = pos['unrealized_pnl']
                    local_pos = self.position_manager.positions.get(symbol)
                    strategy_info = local_pos.strategy if local_pos else "Unknown"
                    self.logger.info(f"  {symbol} ({strategy_info}): size={pos['size']:.4f}, entry=${pos['entry_price']:.2f}, PnL=${pnl:.2f}")
            else:
                self.logger.info("No open positions on exchange")
                
        except Exception as e:
            self.logger.error(f"Error syncing positions: {str(e)}")
    
    async def monitor_positions(self):
        """Monitor open positions and close if stop-loss/take-profit hit"""
        try:
            user_state = self.hl_client.get_user_state()
            if not user_state:
                return
            
            mids = self.hl_client.get_all_mids()
            strategy_configs = self.config.get('strategies', {})
            
            for pos in user_state.get("assetPositions", []):
                position = pos.get("position", {})
                size = float(position.get("szi", 0))
                if size == 0:
                    continue
                    
                symbol = position.get("coin", "")
                entry_price = float(position.get("entryPx", 0))
                current_price = mids.get(symbol)
                # Use exchange-provided unrealized PnL (already accounts for leverage)
                unrealized_pnl = float(position.get("unrealizedPnl", 0))
                
                if current_price is None:
                    continue
                
                is_long = size > 0
                
                # Get strategy-specific stops from tracked position
                local_position = self.position_manager.positions.get(symbol)
                if local_position and local_position.strategy != "Unknown (from exchange)":
                    strategy_name = local_position.strategy.lower()
                    if "momentum" in strategy_name:
                        config = strategy_configs.get('momentum', {})
                    elif "altrank" in strategy_name:
                        config = strategy_configs.get('altrank', {})
                    elif "reversal" in strategy_name:
                        config = strategy_configs.get('reversal', {})
                    else:
                        config = {}
                    stop_loss_pct = config.get('stop_loss_percent', 3.0)
                    take_profit_pct = config.get('target_profit_percent', 8.0)
                else:
                    # Default values for untracked positions
                    stop_loss_pct = 3.0
                    take_profit_pct = 8.0
                
                # Calculate PnL percentage (same formula regardless of direction)
                if is_long:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                
                should_close = False
                close_reason = ""
                
                # Check stop loss (negative PnL exceeds threshold)
                if pnl_pct <= -stop_loss_pct:
                    should_close = True
                    close_reason = "stop_loss"
                    self.logger.warning(f"Stop loss hit for {symbol} ({'long' if is_long else 'short'}): {pnl_pct:.2f}% (limit: -{stop_loss_pct}%)")
                    
                # Check take profit (positive PnL exceeds threshold)
                elif pnl_pct >= take_profit_pct:
                    should_close = True
                    close_reason = "take_profit"
                    self.logger.info(f"Take profit hit for {symbol} ({'long' if is_long else 'short'}): {pnl_pct:.2f}% (target: +{take_profit_pct}%)")
                
                if should_close:
                    # Place close order (buy if short, sell if long)
                    close_is_buy = not is_long
                    result = self.hl_client.place_market_order(symbol, close_is_buy, abs(size), reduce_only=True)
                    
                    # Verify close was successful
                    await asyncio.sleep(1)
                    new_state = self.hl_client.get_user_state()
                    still_open = False
                    if new_state:
                        for p in new_state.get("assetPositions", []):
                            if p.get("position", {}).get("coin") == symbol:
                                if float(p.get("position", {}).get("szi", 0)) != 0:
                                    still_open = True
                                    break
                    
                    if not still_open:
                        self.logger.info(f"Position {symbol} closed successfully via {close_reason}")
                        
                        # Determine WIN/LOSS based on calculated PnL percentage (direction-aware)
                        is_win = pnl_pct > 0
                        
                        # Update database if we have a tracked trade with valid ID
                        if local_position and local_position.trade_id > 0:
                            self.db.update_trade(local_position.trade_id, {
                                'exit_price': current_price,
                                'exit_time': time.time(),
                                'pnl': unrealized_pnl,  # Use exchange-provided PnL
                                'pnl_percent': pnl_pct,
                                'status': 'WIN' if is_win else 'LOSS',
                                'exit_reason': close_reason
                            })
                        
                        # Update risk manager with realized PnL from exchange
                        self.risk_manager.update_daily_pnl(unrealized_pnl)
                        
                        # Remove from position tracker
                        if symbol in self.position_manager.positions:
                            del self.position_manager.positions[symbol]
                    else:
                        self.logger.error(f"Failed to close position {symbol} - still open on exchange")
                    
        except Exception as e:
            self.logger.error(f"Error monitoring positions: {str(e)}")

    async def check_connection(self):
        try:
            coins = self.lc_client.get_coins_list(limit=5)
            if coins:
                self.logger.info(f"LunarCrush connected - {len(coins)} coins available")
            
            is_test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
            if is_test_mode:
                self.logger.info("Hyperliquid connection - test mode")
            else:
                state = self.hl_client.get_user_state()
                if state:
                    balance = state.get('marginSummary', {}).get('accountValue', 0)
                    self.logger.info(f"Hyperliquid connected - Balance: ${float(balance):.2f}")
        except Exception as e:
            self.logger.error(f"Connection check failed: {str(e)}")

    async def execute_trade(self, signal: Dict):
        symbol = signal['symbol']
        signal_type = signal.get('signal_type', 'buy')
        side = 'buy' if signal_type == 'buy' else 'sell'
        strategy_name = signal.get('strategy', 'Unknown')
        
        self.logger.info(f"Executing trade: {side} {symbol} ({strategy_name})")
        
        try:
            strategy_config = {}
            for strat in self.strategies:
                if strat.name == strategy_name:
                    strategy_config = strat.config
                    break
            
            is_test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
            
            # Get real account value from Hyperliquid if in live mode
            if is_test_mode:
                available_capital = float(self.risk_manager.initial_capital)
            else:
                available_capital = float(self.hl_client.get_account_value())
                if available_capital <= 0:
                    self.logger.error("Could not get account value from Hyperliquid")
                    return
            
            # Get current price from Hyperliquid
            mids = self.hl_client.get_all_mids()
            entry_price = mids.get(symbol)
            
            if entry_price is None:
                self.logger.warning(f"Symbol {symbol} not available on Hyperliquid, skipping")
                return
            
            current_positions = self.position_manager.get_position_count()
            
            # Check risk limits
            if not self.risk_manager.can_open_position(current_positions, available_capital):
                self.logger.warning(f"Risk limits prevent opening position on {symbol}")
                return
            
            # Calculate position size
            size = self.risk_manager.calculate_position_size(
                strategy_config, 
                available_capital, 
                entry_price,
                current_positions
            )
            
            if is_test_mode:
                # In test mode, just record in database
                trade_id = self.db.log_trade({
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'size': size * entry_price,  # size in USD for database
                    'strategy': strategy_name,
                    'status': 'OPEN',
                    'timestamp': time.time(),
                    'stop_loss': strategy_config.get('stop_loss_percent'),
                    'take_profit': strategy_config.get('target_profit_percent')
                })
                self.logger.info(f"TEST TRADE LOGGED: {side} {size:.4f} {symbol} @ ${entry_price:.2f}")
            else:
                # Live trade
                is_buy = (side == 'buy')
                order_result = self.hl_client.place_market_order(symbol, is_buy, size)
                
                if order_result and order_result.get('status') == 'ok':
                    # Log to database
                    trade_id = self.db.log_trade({
                        'symbol': symbol,
                        'side': side,
                        'entry_price': entry_price,
                        'size': size * entry_price,
                        'strategy': strategy_name,
                        'status': 'OPEN',
                        'timestamp': time.time(),
                        'leverage': strategy_config.get('leverage', 1),
                        'stop_loss': strategy_config.get('stop_loss_percent'),
                        'take_profit': strategy_config.get('target_profit_percent')
                    })
                    
                    # Track in position manager
                    # Note: monitor_positions will handle closing based on these targets
                    from position_manager import Position
                    # Calculate stop and target prices
                    sl_pct = strategy_config.get('stop_loss_percent', 3.0)
                    tp_pct = strategy_config.get('target_profit_percent', 8.0)
                    
                    if is_buy:
                        stop_loss = entry_price * (1 - sl_pct / 100)
                        take_profit = entry_price * (1 + tp_pct / 100)
                    else:
                        stop_loss = entry_price * (1 + sl_pct / 100)
                        take_profit = entry_price * (1 - tp_pct / 100)
                        
                    position = Position(
                        trade_id=trade_id,
                        symbol=symbol,
                        strategy=strategy_name,
                        entry_price=entry_price,
                        size=size,
                        leverage=strategy_config.get('leverage', 1),
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        entry_time=time.time()
                    )
                    position.is_long = is_buy
                    self.position_manager.positions[symbol] = position
                    
                    self.logger.info(f"LIVE TRADE EXECUTED: {side} {size:.4f} {symbol} @ ${entry_price:.2f}")
                else:
                    self.logger.error(f"Failed to execute live trade for {symbol}: {order_result}")
                    
        except Exception as e:
            self.logger.error(f"Error executing trade: {str(e)}")

    def stop(self):
        self.is_running = False
        self.logger.info("Stopping trading bot...")

if __name__ == "__main__":
    bot = TradingBot()
    asyncio.run(bot.start())
