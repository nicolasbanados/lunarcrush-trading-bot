"""
Simple script to test LunarCrush strategies without executing trades
"""
import asyncio
import sys
import os
import json
from datetime import datetime

from lunarcrush_client import LunarCrushClient
from strategies.momentum_strategy import MomentumStrategy
from strategies.altrank_strategy import AltRankStrategy
from strategies.reversal_strategy import ReversalStrategy

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config/config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

async def test_strategies():
    print("=" * 70)
    print("🧪 LUNARCRUSH TRADING BOT - STRATEGY TESTING")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Mode: TEST (No real trades will be executed)\n")
    
    # Load config
    try:
        config = load_config()
        print("✅ Configuration loaded")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Initialize LunarCrush client
    try:
        api_key = os.getenv('LUNARCRUSH_API_KEY')
        if not api_key:
            raise ValueError("LUNARCRUSH_API_KEY not found in environment")
        lc_client = LunarCrushClient(api_key)
        print("✅ LunarCrush client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LunarCrush client: {e}")
        print("💡 Make sure LUNARCRUSH_API_KEY is set in environment variables")
        return
    
    # Fetch market data from LunarCrush
    print("\n📡 Fetching market data from LunarCrush API...")
    try:
        market_data = lc_client.get_coins_list(sort="galaxy_score", limit=50)
        print(f"✅ Fetched data for {len(market_data)} coins\n")
    except Exception as e:
        print(f"❌ Failed to fetch market data: {e}")
        return
    
    # Initialize strategies with their configs
    strategies_config = config.get("strategies", {})
    strategies = [
        ("momentum", MomentumStrategy(strategies_config.get("momentum", {}))),
        ("altrank", AltRankStrategy(strategies_config.get("altrank", {}))),
        ("reversal", ReversalStrategy(strategies_config.get("reversal", {})))
    ]
    
    total_signals = 0
    
    # Test each strategy
    for strategy_key, strategy in strategies:
        print("\n" + "=" * 70)
        print(f"📊 Testing: {strategy.name}")
        print("=" * 70)
        
        if not strategy.enabled:
            print("⚠️ Strategy is disabled in config")
            continue
        
        try:
            signals = strategy.generate_signals(market_data)
            signal_count = len(signals)
            total_signals += signal_count
            
            if signal_count == 0:
                print("⚠️ No signals generated (market might be quiet)")
                continue
            
            print(f"✅ Generated {signal_count} signal(s)\n")
            
            # Show top 3 signals
            for i, signal in enumerate(signals[:3], 1):
                print(f"Signal #{i}:")
                print(f"  Symbol:     {signal.get('symbol', 'N/A')}")
                print(f"  Side:       {signal.get('side', 'N/A')}")
                print(f"  Confidence: {signal.get('confidence', 'N/A'):.2f}")
                print(f"  Leverage:   {strategy.leverage}x")
                print(f"  Target:     +{strategy.target_profit_percent}%")
                print(f"  Stop Loss:  -{strategy.stop_loss_percent}%")
                print()
                
        except Exception as e:
            print(f"❌ Strategy error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"Total signals generated: {total_signals}")
    print(f"Strategies tested: {len(strategies)}")
    print("\n✅ Test completed successfully!")
    print("💡 These signals would be executed in live mode")

if __name__ == "__main__":
    try:
        asyncio.run(test_strategies())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
