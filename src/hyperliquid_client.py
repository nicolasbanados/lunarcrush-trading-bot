"""
Hyperliquid Client Wrapper
Handles trading operations on Hyperliquid DEX
"""

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account import Account
from typing import Dict, List, Optional, Tuple
import logging
import time
import math

logger = logging.getLogger(__name__)


def format_price(price: float, sz_decimals: int, is_spot: bool = False) -> float:
    """
    Format price per Hyperliquid rules:
    - Max 5 significant figures
    - Max (MAX_DECIMALS - szDecimals) decimal places
    
    Args:
        price: The price to format
        sz_decimals: The szDecimals for this asset
        is_spot: Whether this is a spot market (uses 8 decimals) vs perp (6 decimals)
        
    Returns:
        Properly formatted price as float
    """
    MAX_DECIMALS = 8 if is_spot else 6
    max_decimals = max(0, MAX_DECIMALS - sz_decimals)
    
    if price == 0:
        return 0.0
    
    # Round to 5 significant figures first
    magnitude = math.floor(math.log10(abs(price)))
    # For 5 significant figures, we want the position at magnitude - 4
    sig_figs = 5
    scale = 10 ** (magnitude - (sig_figs - 1))
    price_sig = round(price / scale) * scale
    
    # Then apply decimal limit
    price_rounded = round(price_sig, max_decimals)
    
    return price_rounded


class HyperliquidClient:
    """Client for interacting with Hyperliquid DEX"""
    
    def __init__(self, private_key: str = None, wallet_address: str = None, use_testnet: bool = False):
        """
        Initialize Hyperliquid client
        
        Args:
            private_key: Private key for signing transactions (reads from HYPERLIQUID_PRIVATE_KEY env if not provided)
            wallet_address: Wallet address (reads from HYPERLIQUID_WALLET_ADDRESS env if not provided)
            use_testnet: Whether to use testnet
        """
        import os
        
        # Read from environment if not provided
        self.private_key = private_key or os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.wallet_address = wallet_address or os.getenv('HYPERLIQUID_WALLET_ADDRESS')
        self.use_testnet = use_testnet
        
        if not self.private_key or not self.wallet_address:
            raise ValueError("Private key and wallet address must be provided or set in environment variables")
        
        # Initialize account
        self.account = Account.from_key(self.private_key)
        
        # Initialize Info and Exchange clients
        base_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
        self.info = Info(base_url, skip_ws=True)
        self.exchange = Exchange(self.account, base_url)
        
        # Cache for metadata
        self.meta_cache = None
        self.meta_cache_time = 0
        self.meta_cache_ttl = 300  # 5 minutes
        
        logger.info(f"Hyperliquid client initialized ({'testnet' if use_testnet else 'mainnet'})")
    
    def get_meta(self, force_refresh: bool = False) -> Dict:
        """
        Get perpetuals metadata (universe and margin tables)
        
        Args:
            force_refresh: Force refresh cache
            
        Returns:
            Metadata dictionary
        """
        if not force_refresh and self.meta_cache and (time.time() - self.meta_cache_time < self.meta_cache_ttl):
            return self.meta_cache
        
        try:
            meta = self.info.meta()
            self.meta_cache = meta
            self.meta_cache_time = time.time()
            return meta
        except Exception as e:
            logger.error(f"Failed to fetch metadata: {e}")
            return {}
    
    def get_all_mids(self) -> Dict[str, float]:
        """
        Get current mid prices for all assets
        
        Returns:
            Dictionary mapping asset names to mid prices
        """
        try:
            mids = self.info.all_mids()
            return {k: float(v) for k, v in mids.items()}
        except Exception as e:
            logger.error(f"Failed to fetch mid prices: {e}")
            return {}
    
    def get_user_state(self) -> Dict:
        """
        Get user's account state (positions, balances, etc.)
        
        Returns:
            User state dictionary
        """
        try:
            state = self.info.user_state(self.wallet_address)
            return state
        except Exception as e:
            logger.error(f"Failed to fetch user state: {e}")
            return {}
    
    def get_open_orders(self) -> List[Dict]:
        """
        Get user's open orders
        
        Returns:
            List of open orders
        """
        try:
            orders = self.info.open_orders(self.wallet_address)
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            return []
    
    def get_asset_index(self, symbol: str) -> Optional[int]:
        """
        Get asset index for a symbol
        
        Args:
            symbol: Asset symbol (e.g., 'BTC', 'ETH')
            
        Returns:
            Asset index or None
        """
        meta = self.get_meta()
        universe = meta.get("universe", [])
        
        for i, asset in enumerate(universe):
            if asset.get("name") == symbol:
                return i
        
        logger.warning(f"Asset {symbol} not found in universe")
        return None
    
    def place_market_order(self, symbol: str, is_buy: bool, size: float, 
                          reduce_only: bool = False) -> Dict:
        """
        Place a market order
        
        Args:
            symbol: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            reduce_only: Whether this is a reduce-only order
            
        Returns:
            Order result
        """
        asset_index = self.get_asset_index(symbol)
        if asset_index is None:
            return {"status": "error", "error": f"Asset {symbol} not found"}
        
        try:
            # Ensure size is a float
            size = float(size)
            
            # Get current mid price
            mids = self.get_all_mids()
            mid_price = mids.get(symbol)
            
            if mid_price is None:
                return {"status": "error", "error": f"No price for {symbol}"}
            
            # For market orders, use a price slightly worse than mid
            # Buy: use mid * 1.01, Sell: use mid * 0.99
            slippage = 0.01
            limit_price = mid_price * (1 + slippage) if is_buy else mid_price * (1 - slippage)
            
            # Format price and size according to asset decimals
            meta = self.get_meta()
            asset_info = meta["universe"][asset_index]
            sz_decimals = int(asset_info.get("szDecimals", 5))
            
            # Round size to appropriate decimals
            rounded_size = round(size, sz_decimals)
            # Format price per Hyperliquid rules (5 sig figs, max decimals)
            rounded_price = format_price(limit_price, sz_decimals)
            
            # Place order - SDK expects floats, not strings
            order_result = self.exchange.order(
                symbol,
                is_buy,
                rounded_size,
                rounded_price,
                {"limit": {"tif": "Ioc"}},  # Immediate or Cancel for market-like behavior
                reduce_only=reduce_only
            )
            
            logger.info(f"Placed {'BUY' if is_buy else 'SELL'} order: {symbol} {rounded_size} @ {rounded_price}")
            return order_result
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {"status": "error", "error": str(e)}
    
    def place_limit_order(self, symbol: str, is_buy: bool, size: float, price: float,
                         reduce_only: bool = False, post_only: bool = False) -> Dict:
        """
        Place a limit order
        
        Args:
            symbol: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            price: Limit price
            reduce_only: Whether this is a reduce-only order
            post_only: Whether to use post-only (ALO)
            
        Returns:
            Order result
        """
        asset_index = self.get_asset_index(symbol)
        if asset_index is None:
            return {"status": "error", "error": f"Asset {symbol} not found"}
        
        try:
            # Ensure types
            size = float(size)
            price = float(price)
            
            meta = self.get_meta()
            asset_info = meta["universe"][asset_index]
            sz_decimals = int(asset_info.get("szDecimals", 5))
            
            rounded_size = round(size, sz_decimals)
            # Format price per Hyperliquid rules (5 sig figs, max decimals)
            rounded_price = format_price(price, sz_decimals)
            
            tif = "Alo" if post_only else "Gtc"
            
            # SDK expects floats, not strings
            order_result = self.exchange.order(
                symbol,
                is_buy,
                rounded_size,
                rounded_price,
                {"limit": {"tif": tif}},
                reduce_only=reduce_only
            )
            
            logger.info(f"Placed {'BUY' if is_buy else 'SELL'} limit order: {symbol} {rounded_size} @ {rounded_price}")
            return order_result
            
        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            return {"status": "error", "error": str(e)}
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """
        Cancel an order
        
        Args:
            symbol: Asset symbol
            order_id: Order ID
            
        Returns:
            Cancel result
        """
        asset_index = self.get_asset_index(symbol)
        if asset_index is None:
            return {"status": "error", "error": f"Asset {symbol} not found"}
        
        try:
            result = self.exchange.cancel(symbol, order_id)
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {"status": "error", "error": str(e)}
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """
        Cancel all orders (optionally for a specific symbol)
        
        Args:
            symbol: Optional asset symbol to cancel orders for
            
        Returns:
            Cancel result
        """
        try:
            open_orders = self.get_open_orders()
            
            if symbol:
                open_orders = [o for o in open_orders if o.get("coin") == symbol]
            
            results = []
            for order in open_orders:
                result = self.cancel_order(order["coin"], order["oid"])
                results.append(result)
            
            logger.info(f"Cancelled {len(results)} orders")
            return {"status": "ok", "cancelled": len(results)}
            
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return {"status": "error", "error": str(e)}
    
    def update_leverage(self, symbol: str, leverage: int, is_cross: bool = False) -> Dict:
        """
        Update leverage for an asset
        
        Args:
            symbol: Asset symbol
            leverage: Leverage value
            is_cross: Whether to use cross margin
            
        Returns:
            Update result
        """
        asset_index = self.get_asset_index(symbol)
        if asset_index is None:
            return {"status": "error", "error": f"Asset {symbol} not found"}
        
        try:
            result = self.exchange.update_leverage(leverage, symbol, is_cross)
            logger.info(f"Updated leverage for {symbol}: {leverage}x ({'cross' if is_cross else 'isolated'})")
            return result
        except Exception as e:
            logger.error(f"Failed to update leverage: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Position data or None
        """
        state = self.get_user_state()
        positions = state.get("assetPositions", [])
        
        for pos in positions:
            position = pos.get("position", {})
            if position.get("coin") == symbol:
                return position
        
        return None
    
    def get_account_value(self) -> float:
        """
        Get total account value
        
        Returns:
            Account value in USD
        """
        state = self.get_user_state()
        margin_summary = state.get("marginSummary", {})
        account_value = float(margin_summary.get("accountValue", 0))
        return account_value
    
    def get_available_balance(self) -> float:
        """
        Get available balance for trading
        
        Returns:
            Available balance in USD
        """
        state = self.get_user_state()
        withdrawable = float(state.get("withdrawable", 0))
        return withdrawable
    
    def place_order(self, symbol: str, side: str, size_usd: float, leverage: int = 1) -> Dict:
        """
        Place an order (wrapper method for main bot)
        
        Args:
            symbol: Asset symbol (e.g., 'BTC', 'ETH')
            side: 'buy' or 'sell'
            size_usd: Position size in USD
            leverage: Leverage to use
            
        Returns:
            Dictionary with 'success' boolean and order details including fill info
        """
        try:
            # Hyperliquid requires minimum order value of $10
            MIN_ORDER_VALUE = 11.0  # Use 11 to have margin for price movement
            
            if size_usd < MIN_ORDER_VALUE:
                logger.warning(f"Order size ${size_usd:.2f} below minimum ${MIN_ORDER_VALUE}, skipping")
                return {'success': False, 'error': f'Order size below minimum ${MIN_ORDER_VALUE}'}
            
            # Update leverage first
            self.update_leverage(symbol, leverage, is_cross=False)
            
            # Get current price
            mids = self.get_all_mids()
            current_price = mids.get(symbol)
            
            if current_price is None:
                logger.error(f"Could not get price for {symbol}")
                return {'success': False, 'error': 'No price available'}
            
            # Calculate size in coins (not USD)
            size_coins = size_usd / current_price
            
            # Get asset info for proper rounding
            asset_index = self.get_asset_index(symbol)
            if asset_index is not None:
                meta = self.get_meta()
                asset_info = meta["universe"][asset_index]
                sz_decimals = int(asset_info.get("szDecimals", 5))
                size_coins = round(size_coins, sz_decimals)
                
                # Verify size is not zero after rounding
                if size_coins <= 0:
                    logger.warning(f"Order size rounds to zero for {symbol}, skipping")
                    return {'success': False, 'error': 'Order size rounds to zero'}
                
                # Recheck USD value after rounding to ensure still above minimum
                actual_usd_value = size_coins * current_price
                if actual_usd_value < MIN_ORDER_VALUE:
                    logger.warning(f"Order value ${actual_usd_value:.2f} below minimum ${MIN_ORDER_VALUE} after rounding, skipping")
                    return {'success': False, 'error': f'Order value ${actual_usd_value:.2f} below minimum after rounding'}
            
            logger.info(f"Placing order: {side} {size_coins:.6f} {symbol} @ ~${current_price:.2f} (${size_usd} notional, {leverage}x leverage)")
            
            # Place market order
            is_buy = (side.lower() == 'buy')
            result = self.place_market_order(
                symbol=symbol,
                is_buy=is_buy,
                size=size_coins,
                reduce_only=False
            )
            
            # Check if order was successful and parse fill information
            if result.get('status') == 'ok':
                response_data = result.get('response', {})
                statuses = response_data.get('data', {}).get('statuses', [])
                
                filled_size = 0.0
                avg_price = current_price
                order_id = None
                
                if statuses:
                    status = statuses[0]
                    # Check for fill information
                    if 'filled' in status:
                        filled_info = status['filled']
                        filled_size = float(filled_info.get('totalSz', 0))
                        avg_price = float(filled_info.get('avgPx', current_price))
                        order_id = filled_info.get('oid')
                        logger.info(f"Order filled: {filled_size} {symbol} @ ${avg_price:.4f}")
                    elif 'resting' in status:
                        # Order is resting (limit order not immediately filled)
                        order_id = status['resting'].get('oid')
                        logger.info(f"Order resting (not filled): {symbol}")
                    elif 'error' in status:
                        error_msg = status.get('error', 'Unknown order error')
                        logger.error(f"Order status error: {error_msg}")
                        return {'success': False, 'error': error_msg, 'result': result}
                
                # For IOC orders, consider success if we got any fill
                if filled_size > 0:
                    return {
                        'success': True,
                        'filled': True,
                        'price': avg_price,
                        'size': filled_size,
                        'size_usd': filled_size * avg_price,
                        'leverage': leverage,
                        'order_id': order_id,
                        'result': result
                    }
                else:
                    # IOC order didn't fill - this is expected sometimes
                    logger.warning(f"IOC order for {symbol} did not fill - no liquidity at price")
                    return {
                        'success': False,
                        'filled': False,
                        'error': 'Order did not fill (IOC)',
                        'result': result
                    }
            else:
                logger.error(f"Order failed: {result}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'result': result
                }
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    # This requires a valid private key and wallet
    # client = HyperliquidClient("YOUR_PRIVATE_KEY", "YOUR_WALLET", use_testnet=True)
    # account_value = client.get_account_value()
    # print(f"Account value: ${account_value:.2f}")
    
    print("Hyperliquid client module loaded successfully")
