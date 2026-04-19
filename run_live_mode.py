"""
Run bot in LIVE MODE with web dashboard
Executes real trades on Hyperliquid
"""
import os
import sys
from threading import Thread
import time

os.environ['TEST_MODE'] = 'false'

print("=" * 70)
print("🚀 LUNARCRUSH BOT - LIVE MODE")
print("=" * 70)
print("⚠️  LIVE TRADING - Real trades will be executed!")
print("💰 Using your Hyperliquid account")
print("📊 Dashboard available in Preview tab\n")

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
        print("🚀 Starting bot in LIVE mode...")
        print("💡 Press Ctrl+C to stop\n")
        
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    api_thread = Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    time.sleep(2)
    
    print(f"📊 Dashboard: Open the 'Preview' tab in Replit")
    print(f"🔗 API Status: Check /api/status endpoint\n")
    print("=" * 70 + "\n")
    
    run_bot()
