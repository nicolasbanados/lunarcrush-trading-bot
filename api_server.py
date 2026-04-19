"""
Simple Flask API to serve bot data to the dashboard
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import Database
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for local dashboard access

db = Database()
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config/config.json')
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), 'dashboard')

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard HTML"""
    return send_from_directory(DASHBOARD_DIR, 'index.html')

@app.route('/logo.png')
def serve_logo():
    """Serve the logo image"""
    return send_from_directory(DASHBOARD_DIR, 'logo.png')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current bot status and metrics"""
    try:
        # Get all trades
        trades = db.get_all_trades()
        open_positions = [t for t in trades if t['status'] == 'OPEN']
        closed_trades = [t for t in trades if t['status'] in ['WIN', 'LOSS']]
        
        # Calculate metrics
        total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        wins = [t for t in closed_trades if t['status'] == 'WIN']
        losses = [t for t in closed_trades if t['status'] == 'LOSS']
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
        
        # Today's trades
        today = datetime.now().date()
        today_trades = [t for t in closed_trades if datetime.fromisoformat(t['timestamp']).date() == today]
        today_pnl = sum(t.get('pnl', 0) for t in today_trades)
        
        return jsonify({
            'balance': 1000 + total_pnl,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / 1000) * 100,
            'today_pnl': today_pnl,
            'today_pnl_pct': (today_pnl / 1000) * 100,
            'win_rate': win_rate,
            'wins': len(wins),
            'losses': len(losses),
            'open_positions': len(open_positions),
            'total_trades': len(closed_trades)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get all open positions"""
    try:
        trades = db.get_all_trades()
        open_positions = [t for t in trades if t['status'] == 'OPEN']
        return jsonify(open_positions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions history"""
    try:
        trades = db.get_all_trades()
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily-summary', methods=['GET'])
def get_daily_summary():
    """Get daily summary for reporting"""
    try:
        trades = db.get_all_trades()
        today = datetime.now().date()
        today_trades = [t for t in trades if datetime.fromisoformat(t['timestamp']).date() == today]
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
