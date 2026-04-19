"""
Simple Flask API to serve bot data to the dashboard
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import Database
from hyperliquid_client import HyperliquidClient
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import time
import hashlib

app = Flask(__name__)
CORS(app)  # Enable CORS for local dashboard access

db = Database()
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '../config/config.json')
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), '../dashboard')
BOT_STATE_FILE = os.path.join(os.path.dirname(__file__), '../config/bot_state.json')

# Initialize Hyperliquid client for real-time data
hl_client = None
try:
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
    if private_key and wallet_address:
        hl_client = HyperliquidClient(private_key, wallet_address, use_testnet=False)
except Exception as e:
    print(f"Warning: Could not initialize Hyperliquid client: {e}")

# Admin password from environment variable
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

def require_admin(f):
    """Decorator to require admin password for protected endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        password = request.headers.get('X-Admin-Password', '')
        if not password and request.is_json:
            password = request.json.get('password', '')
        if not ADMIN_PASSWORD:
            return jsonify({'error': 'Admin password not configured', 'auth_required': True}), 401
        if password != ADMIN_PASSWORD:
            return jsonify({'error': 'Invalid password', 'auth_required': True}), 401
        return f(*args, **kwargs)
    return decorated_function

# Bot scan tracking
bot_scan_state = {
    'last_scan': None,
    'next_scan': None,
    'api_calls': 0,
    'scan_interval': 180
}

def update_scan_time():
    bot_scan_state['last_scan'] = time.time()
    bot_scan_state['next_scan'] = time.time() + bot_scan_state['scan_interval']
    bot_scan_state['api_calls'] += 1

# Initialize bot state file if it doesn't exist
if not os.path.exists(BOT_STATE_FILE):
    with open(BOT_STATE_FILE, 'w') as f:
        json.dump({'status': 'running', 'pause_requested': False}, f)

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard HTML"""
    return send_from_directory(DASHBOARD_DIR, 'index.html')

@app.route('/logo.png')
def serve_logo():
    """Serve the logo image"""
    return send_from_directory(DASHBOARD_DIR, 'logo.png')

@app.route('/api/update-scan', methods=['POST'])
def api_update_scan():
    """Update scan timing from main bot"""
    update_scan_time()
    return jsonify({'status': 'ok'})

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current bot status and metrics"""
    try:
        # Get real data directly from Hyperliquid
        real_balance = 0.0
        real_positions = []
        unrealized_pnl = 0.0
        closed_pnl = 0.0
        today_closed_pnl = 0.0
        wins = 0
        losses = 0
        
        if hl_client:
            try:
                real_balance = hl_client.get_account_value()
                user_state = hl_client.get_user_state()
                
                # Get unrealized PnL from open positions
                if user_state:
                    positions = user_state.get("assetPositions", [])
                    for pos in positions:
                        position = pos.get("position", {})
                        if float(position.get("szi", 0)) != 0:
                            real_positions.append({
                                'symbol': position.get("coin", ""),
                                'size': float(position.get("szi", 0)),
                                'entry_price': float(position.get("entryPx", 0)),
                                'unrealized_pnl': float(position.get("unrealizedPnl", 0)),
                                'leverage': float(position.get("leverage", {}).get("value", 1))
                            })
                            unrealized_pnl += float(position.get("unrealizedPnl", 0))
                
                # Get closed PnL from fills (real trade history)
                fills = hl_client.info.user_fills(hl_client.wallet_address)
                today = datetime.now().date()
                
                for fill in fills:
                    pnl = float(fill.get('closedPnl', 0))
                    closed_pnl += pnl
                    
                    # Check if trade was today
                    fill_time = fill.get('time', 0)
                    if fill_time:
                        fill_date = datetime.fromtimestamp(fill_time / 1000).date()
                        if fill_date == today:
                            today_closed_pnl += pnl
                    
                    # Count wins/losses (only for closing trades with significant PnL)
                    if 'Close' in fill.get('dir', ''):
                        if pnl > 0:
                            wins += 1
                        elif pnl < -0.01:  # Ignore tiny fees
                            losses += 1
                            
            except Exception as e:
                print(f"Error fetching Hyperliquid data: {e}")
        
        # Calculate total PnL (closed + unrealized)
        total_pnl = closed_pnl + unrealized_pnl
        today_pnl = today_closed_pnl + unrealized_pnl
        
        # Win rate
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Get bot state
        bot_status = 'running'
        if os.path.exists(BOT_STATE_FILE):
            with open(BOT_STATE_FILE, 'r') as f:
                state = json.load(f)
                if state.get('status') == 'stopped':
                    bot_status = 'stopped'
                elif state.get('pause_requested', False):
                    bot_status = 'paused'
                else:
                    bot_status = 'running'
        
        # Calculate scan timing
        last_scan_str = '--:--:--'
        next_scan_str = '--'
        if bot_scan_state['last_scan']:
            last_scan_str = datetime.fromtimestamp(bot_scan_state['last_scan']).strftime('%H:%M:%S')
        if bot_scan_state['next_scan']:
            remaining = max(0, int(bot_scan_state['next_scan'] - time.time()))
            mins, secs = divmod(remaining, 60)
            next_scan_str = f"{mins}:{secs:02d}"
        
        # Calculate starting balance dynamically (current balance minus all PnL = original deposit)
        # This gives us the actual starting balance based on real data
        starting_balance = real_balance - total_pnl
        if starting_balance <= 0:
            starting_balance = real_balance  # Fallback if calculation fails
        
        # Calculate percentages based on starting balance
        total_pnl_pct = (total_pnl / starting_balance) * 100 if starting_balance > 0 else 0
        today_pnl_pct = (today_pnl / starting_balance) * 100 if starting_balance > 0 else 0
        
        return jsonify({
            'balance': real_balance,
            'starting_balance': starting_balance,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'today_pnl': today_pnl,
            'today_pnl_pct': today_pnl_pct,
            'win_rate': win_rate,
            'wins': wins,
            'losses': losses,
            'open_positions': len(real_positions),
            'total_trades': total_trades,
            'bot_status': bot_status,
            'last_scan': last_scan_str,
            'next_scan': next_scan_str,
            'api_calls': bot_scan_state['api_calls'],
            'positions_detail': real_positions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get all open positions from Hyperliquid exchange"""
    try:
        positions = []
        
        # Get real positions from Hyperliquid
        if hl_client:
            try:
                user_state = hl_client.get_user_state()
                mids = hl_client.get_all_mids()
                
                if user_state:
                    for pos in user_state.get("assetPositions", []):
                        position = pos.get("position", {})
                        size = float(position.get("szi", 0))
                        if size != 0:
                            symbol = position.get("coin", "")
                            entry_price = float(position.get("entryPx", 0))
                            current_price = mids.get(symbol, entry_price)
                            unrealized_pnl = float(position.get("unrealizedPnl", 0))
                            
                            # Get leverage value
                            lev = position.get("leverage", {})
                            if isinstance(lev, dict):
                                leverage = float(lev.get("value", 1))
                            else:
                                leverage = float(lev) if lev else 1
                            
                            positions.append({
                                'symbol': symbol,
                                'side': 'long' if size > 0 else 'short',
                                'size': abs(size),
                                'entry_price': entry_price,
                                'current_price': current_price,
                                'unrealized_pnl': unrealized_pnl,
                                'leverage': leverage,
                                'status': 'OPEN'
                            })
            except Exception as e:
                print(f"Error fetching positions from Hyperliquid: {e}")
        
        # Fall back to database if no Hyperliquid client
        if not positions:
            trades = db.get_all_trades()
            positions = [t for t in trades if t['status'] == 'OPEN']
        
        return jsonify(positions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions history from Hyperliquid"""
    try:
        trades = []
        
        if hl_client:
            try:
                fills = hl_client.info.user_fills(hl_client.wallet_address)
                
                for fill in fills:
                    trade_time = fill.get('time', 0)
                    if trade_time:
                        time_str = datetime.fromtimestamp(trade_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        time_str = '--'
                    
                    trades.append({
                        'time': time_str,
                        'symbol': fill.get('coin', ''),
                        'side': fill.get('dir', ''),
                        'price': float(fill.get('px', 0)),
                        'size': float(fill.get('sz', 0)),
                        'value': float(fill.get('ntl', 0)),
                        'fee': float(fill.get('fee', 0)),
                        'pnl': float(fill.get('closedPnl', 0))
                    })
            except Exception as e:
                print(f"Error fetching trades from Hyperliquid: {e}")
        
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily-summary', methods=['GET'])
def get_daily_summary():
    """Get daily summary for reporting"""
    try:
        trades = db.get_all_trades()
        today = datetime.now().date()
        def get_trade_date(t):
            ts = t.get('timestamp')
            if ts is None:
                return None
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts).date()
            elif isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts).date()
                except:
                    return None
            return None
        today_trades = [t for t in trades if get_trade_date(t) == today]
        
        # Strategy breakdown
        strategies = {}
        for trade in today_trades:
            strat = trade.get('strategy', 'unknown')
            if strat not in strategies:
                strategies[strat] = 0
            strategies[strat] += trade.get('pnl', 0)
        
        return jsonify({
            'total_trades': len(today_trades),
            'wins': len([t for t in today_trades if t['status'] == 'WIN']),
            'losses': len([t for t in today_trades if t['status'] == 'LOSS']),
            'strategies': strategies
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-config', methods=['POST'])
@require_admin
def update_config():
    """Update strategy configuration"""
    try:
        data = request.json
        strategies = data.get('strategies', {})
        
        # Load current config
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Update strategy weights and parameters
        for strategy_name, params in strategies.items():
            if strategy_name in config['strategies']:
                config['strategies'][strategy_name]['capital_allocation'] = params['weight'] / 100
                config['strategies'][strategy_name]['leverage'] = params['leverage']
                config['strategies'][strategy_name]['enabled'] = params['enabled']
        
        # Save updated config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully',
            'config': config
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-config', methods=['GET'])
def get_config():
    """Get current strategy configuration"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/pause', methods=['POST'])
@require_admin
def pause_bot():
    """Pause bot after closing all open positions"""
    try:
        with open(BOT_STATE_FILE, 'r') as f:
            state = json.load(f)
        
        state['pause_requested'] = True
        state['status'] = 'pausing'
        
        with open(BOT_STATE_FILE, 'w') as f:
            json.dump(state, f)
        
        return jsonify({
            'success': True,
            'message': 'Bot will pause after closing all positions',
            'status': 'pausing'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/resume', methods=['POST'])
@require_admin
def resume_bot():
    """Resume bot trading"""
    try:
        with open(BOT_STATE_FILE, 'r') as f:
            state = json.load(f)
        
        state['pause_requested'] = False
        state['status'] = 'running'
        
        with open(BOT_STATE_FILE, 'w') as f:
            json.dump(state, f)
        
        return jsonify({
            'success': True,
            'message': 'Bot resumed',
            'status': 'running'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/stop', methods=['POST'])
@require_admin
def stop_bot():
    """Stop bot immediately and close all positions"""
    try:
        with open(BOT_STATE_FILE, 'r') as f:
            state = json.load(f)
        
        state['pause_requested'] = False
        state['status'] = 'stopped'
        state['close_all'] = True
        
        with open(BOT_STATE_FILE, 'w') as f:
            json.dump(state, f)
        
        return jsonify({
            'success': True,
            'message': 'Bot stopped - closing all positions',
            'status': 'stopped'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/update', methods=['POST'])
@require_admin
def update_strategy_config():
    """Update strategy sensitivity and parameters"""
    try:
        data = request.json
        
        # Load current config
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Update momentum strategy
        if 'momentum' in data:
            m = data['momentum']
            config['strategies']['momentum']['capital_allocation'] = m['allocation'] / 100
            config['strategies']['momentum']['leverage'] = m['leverage']
            config['strategies']['momentum']['social_volume_min'] = m['social_volume_min']
            config['strategies']['momentum']['sentiment_min'] = m['sentiment_min']
        
        # Update altrank strategy
        if 'altrank' in data:
            a = data['altrank']
            config['strategies']['altrank']['capital_allocation'] = a['allocation'] / 100
            config['strategies']['altrank']['leverage'] = a['leverage']
            config['strategies']['altrank']['rank_improve_min'] = a['rank_improve_min']
            config['strategies']['altrank']['top_coins'] = a['top_coins']
        
        # Update reversal strategy
        if 'reversal' in data:
            r = data['reversal']
            config['strategies']['reversal']['capital_allocation'] = r['allocation'] / 100
            config['strategies']['reversal']['leverage'] = r['leverage']
            config['strategies']['reversal']['price_drop_min'] = r['price_drop_min']
            config['strategies']['reversal']['galaxy_score_min'] = r['galaxy_score_min']
        
        # Save updated config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
