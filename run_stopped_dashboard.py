"""Simple dashboard showing STOPPED status"""
import sys
sys.path.insert(0, 'src')

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

DASHBOARD_DIR = 'dashboard'

@app.route('/')
def serve_dashboard():
    return send_from_directory(DASHBOARD_DIR, 'index.html')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(DASHBOARD_DIR, 'logo.png')

@app.route('/api/status')
def get_status():
    return jsonify({
        'balance': 999.86,
        'total_pnl': 0,
        'total_pnl_pct': 0,
        'today_pnl': 0,
        'today_pnl_pct': 0,
        'win_rate': 0,
        'wins': 0,
        'losses': 0,
        'open_positions': 0,
        'total_trades': 0,
        'bot_status': 'stopped',
        'last_scan': '--:--:--',
        'next_scan': '--',
        'api_calls': 0
    })

if __name__ == '__main__':
    print("=" * 60)
    print("BOT STATUS: STOPPED")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)
