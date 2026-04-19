# LunarCrush Trading Bot (LCTB)

## Overview
An automated cryptocurrency trading bot that uses LunarCrush social intelligence data to generate trading signals and execute trades on Hyperliquid perpetuals exchange.

## Current State
- **Status**: STOPPED - Bot stopped by user
- **Dashboard**: Offline (Workflow stopped)
- **Strategies**: 3 active (Social Momentum, AltRank Breakout, Galaxy Reversal)
- **Fear & Greed Monitor**: Running - sends email when index > 45

## Project Structure
```
├── src/
│   ├── main.py           # Main trading bot logic
│   ├── database.py       # SQLite database for trades/signals
│   ├── api_server.py     # Flask API server for dashboard
│   ├── lunarcrush_client.py  # LunarCrush API client
│   ├── hyperliquid_client.py # Hyperliquid exchange client
│   ├── risk_manager.py   # Position sizing and risk limits
│   └── position_manager.py   # Position tracking
├── strategies/
│   ├── base_strategy.py      # Base strategy class
│   ├── momentum_strategy.py  # Social Momentum Scalping
│   ├── altrank_strategy.py   # AltRank Breakout Hunter
│   └── reversal_strategy.py  # Galaxy Score Reversal
├── dashboard/
│   └── index.html        # Trading dashboard UI
├── config/
│   └── config.json       # Bot configuration
├── run_test_mode.py      # Test mode launcher
└── data/                 # Database storage
```

## Strategies

### 1. Social Momentum Scalping
- Entry: Social volume spike (+40%), interactions spike (+30%), high sentiment (>58%)
- Target: Quick scalp trades on social momentum

### 2. AltRank Breakout Hunter
- Entry: Low AltRank with improving metrics
- Target: Coins breaking out based on AltRank improvement

### 3. Galaxy Score Reversal
- Entry: Price dip with high Galaxy Score (>65)
- Target: Mean reversion on socially strong coins

## Running the Bot

### Test Mode (No real trades)
```bash
python run_test_mode.py
```
- Simulates all trades
- Records in database
- Dashboard available on port 5000

### Live Mode (Requires Hyperliquid credentials)
```bash
python -m src.main
```

## Required Secrets
- `LUNARCRUSH_API_KEY` - LunarCrush API access
- `HYPERLIQUID_PRIVATE_KEY` - Hyperliquid wallet private key (for live trading)
- `HYPERLIQUID_WALLET_ADDRESS` - Hyperliquid wallet address
- `ADMIN_PASSWORD` - Password for dashboard admin controls

## Security
- Dashboard is public read-only (anyone can view stats/trades)
- Bot controls require ADMIN_PASSWORD authentication
- Protected actions: Pause, Resume, Stop, Apply Changes

## Risk Management
- Max positions: 3
- Daily loss limit: 8%
- Position size capped at 80% of available capital
- Configurable leverage per strategy

## Fear & Greed Monitor
- Checks crypto Fear & Greed Index every 4 hours
- Sends email notification when index rises above 45
- Uses Replit Mail integration (sends to verified Replit email)
- File: `src/fear_greed_monitor.py`
- State file: `data/fear_greed_state.json`

## Recent Changes
- 2025-12-18: Added Fear & Greed Monitor - email alerts when market sentiment improves
- 2025-12-18: Bot PAUSED after circuit breaker activation (-33% total loss)
- 2025-12-18: DOGE closed at -$154.44 loss, NEAR remaining (user to close manually)
- 2025-12-17: OPTIMIZED - Made bot more conservative after 0% win rate analysis
  - Reduced leverage: Momentum 4x→3x, AltRank 3x→2x, Reversal 3x→2x
  - Widened stop-losses: 2.5%→5%, 3.5%→6%, 4%→7%
  - Tightened entry thresholds: sentiment 52→60, social volume 25%→40%
  - Increased take-profit targets for better risk/reward ratio
- 2025-12-16: FIXED - Bot now respects Pause/Resume controls from dashboard
- 2025-12-16: Added get_bot_state() to read pause status from bot_state.json
- 2025-12-16: When paused, bot monitors positions but does not open new trades
- 2025-12-16: Added minimum order value validation ($11) in HyperliquidClient.place_order()
- 2025-12-16: Added size rounding using szDecimals from asset metadata
- 2025-12-16: RiskManager now enforces $15 minimum position value 
- 2025-12-16: CRITICAL FIX - Fixed Hyperliquid SDK order placement (SDK expects floats, not strings for sz/limit_px)
- 2025-12-16: Fixed strategy config key mismatch (momentum/altrank/reversal instead of social_momentum/altrank_breakout/galaxy_reversal)
- 2025-12-16: Added sync_positions_with_exchange() to synchronize local state with Hyperliquid
- 2025-12-16: Added monitor_positions() with strategy-specific stop-loss/take-profit
- 2025-12-16: Updated execute_trade() to use real account value and verify order fills
- 2025-12-16: API positions endpoint now returns real Hyperliquid positions
- 2025-12-16: Position closures now properly update database and risk manager
- 2025-12-15: Added password protection for admin controls
- 2025-12-15: Dashboard now public read-only, controls require authentication
- 2025-12-15: Fixed test mode signal_type to side translation
- 2025-12-15: Fixed database log_trade method compatibility
- 2025-12-15: Added custom LCTB logo to dashboard
- 2025-12-15: Fixed RiskManager method signatures
