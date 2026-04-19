"""
Run bot in TEST MODE with web dashboard
Perfect for testing strategies before using real funds
"""
import os
import sys
from threading import Thread
import time

# Set test mode environment variable
os.environ['TEST_MODE'] = 'true'
os.environ['SKIP_HYPERLIQUID'] = 'true'

# Dummy Hyperliquid credentials for test mode
if not os.getenv('HYPERLIQUID_PRIVATE_KEY'):
    os.environ['HYPERLIQUID_PRIVATE_KEY'] = '0x0000000000000000000000000000000000000000000000000000000000000001'
if not os.getenv('HYPERLIQUID_WALLET_ADDRESS'):
    os.environ['HYPERLIQUID_WALLET_ADDRESS'] = '0x0000000000000000000000000000000000000000'

print("=" * 70)
print("🧪 LUNARCRUSH BOT - TEST MODE WITH DASHBOARD")
print("=" * 70)
print("⚠️  Running in TEST MODE - No real trades will be executed")
print("✅ You don't need Hyperliquid configured for this")
print("✅ Bot will simulate all trades")
print("✅ Dashboard will be available in Preview tab\n")

# Import modules
sys.path.insert(0, 'src')

def run_api_server():
    """Run Flask API server in background"""
    try:
        from api_server import app
        print("🌐 Starting API server on port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ API server error: {e}")

def run_bot():
    """Run trading bot"""
    try:
        from main import TradingBot
        import asyncio
        
        print("🤖 Initializing trading bot...")
        bot = TradingBot()
        print("🚀 Starting bot in test mode...")
        print("💡 Press Ctrl+C to stop\n")
        
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Start API server in background thread
    api_thread = Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Wait for API server to start
    time.sleep(2)
    
    # Get Repl URL
    repl_slug = os.getenv('REPL_SLUG', 'your-repl')
    repl_owner = os.getenv('REPL_OWNER', 'username')
    
    print(f"📊 Dashboard: Open the 'Preview' tab in Replit")
    print(f"🔗 API Status: Check /api/status endpoint\n")
    print("=" * 70 + "\n")
    
    # Start bot (main thread)
    run_bot()
