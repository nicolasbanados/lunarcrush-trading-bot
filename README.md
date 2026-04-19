# 🌙 LunarCrush Trading Bot

**Automated cryptocurrency trading bot powered by LunarCrush social intelligence data.**

Built for the LunarCrush internal trading competition (Dec 2025) to demonstrate the value of social sentiment data in generating trading alpha.

---

## 🎯 Project Overview

This bot implements **3 complementary trading strategies** that leverage LunarCrush's proprietary metrics (Galaxy Score, AltRank, Social Volume) to identify high-probability trading opportunities on Hyperliquid perpetuals exchange.

### Strategies

1. **Social Momentum Scalping** (40% capital allocation)
   - Captures explosive social volume spikes that precede price movements
   - Target: +6% | Stop: -2.5% | Leverage: 5x
   - Trade duration: 1-4 hours

2. **AltRank Breakout Hunter** (30% capital allocation)
   - Identifies altcoins with rapid ranking improvements
   - Target: +12% | Stop: -3.5% | Leverage: 4x
   - Trade duration: 2-8 hours

3. **Galaxy Score Reversal** (20% capital allocation)
   - Exploits divergences between price action and social fundamentals
   - Target: +10% | Stop: -4% | Leverage: 3x
   - Trade duration: 4-12 hours

---

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| **Net ROI (4 days)** | +30% to +50% |
| **Win Rate** | > 55% |
| **Max Drawdown** | < 15% |
| **Daily Trades** | 15-25 |

---

## 🛠️ Technical Architecture

```
┌─────────────────────────────────────┐
│  Data Layer                         │
│  - LunarCrush API V2                │
│  - Real-time social metrics         │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  Signal Engine                      │
│  - 3 Strategy Modules               │
│  - Python 3.11                      │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  Risk Gatekeeper                    │
│  - Position sizing                  │
│  - Stop loss enforcement            │
│  - Portfolio limits                 │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  Execution Layer                    │
│  - Hyperliquid SDK                  │
│  - Non-custodial wallet             │
└─────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- LunarCrush API Key (V2)
- Hyperliquid wallet with funds on Arbitrum
- Ubuntu 22.04 VPS (recommended)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd lunarcrush-trading-bot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your API keys
```

### Running the Bot

```bash
# Start main bot
python src/main.py

# Start API server (for dashboard)
python src/api_server.py

# Open dashboard
open dashboard/index.html
```

---

## 📈 Dashboard Features

The included web dashboard provides:

- **Real-time portfolio tracking** with live PnL updates
- **Active positions monitor** with entry/exit prices
- **Complete transaction history** with filters
- **Daily summary report** for management updates
- **Export functionality** (CSV, TXT reports)
- **Performance charts** showing portfolio growth

Access at: `http://localhost:8080` (after starting simple HTTP server)

---

## 📁 Project Structure

```
lunarcrush-trading-bot/
├── src/
│   ├── main.py                    # Main bot orchestrator
│   ├── lunarcrush_client.py       # LunarCrush API wrapper
│   ├── hyperliquid_client.py      # Hyperliquid SDK wrapper
│   ├── database.py                # SQLite persistence
│   ├── risk_manager.py            # Risk controls
│   ├── position_manager.py        # Position lifecycle
│   ├── api_server.py              # Flask API for dashboard
│   └── strategies/
│       ├── base_strategy.py
│       ├── momentum_strategy.py
│       ├── altrank_strategy.py
│       └── reversal_strategy.py
├── dashboard/
│   └── index.html                 # Web dashboard
├── config/
│   └── config.json                # Bot configuration
├── DEPLOYMENT_GUIDE.md            # Detailed deployment instructions
└── README.md                      # This file
```

---

## ⚠️ Risk Management

The bot implements **3 layers of risk protection**:

### Layer 1: Per-Trade
- Hard stop loss on every order (-2.5% to -4%)
- Dynamic position sizing based on volatility
- Maximum leverage cap (5x)

### Layer 2: Portfolio
- Daily drawdown limit (-15% hard stop)
- Maximum 5 concurrent positions
- Correlation checks to avoid overexposure

### Layer 3: Systemic
- Emergency kill switch (flatten all positions)
- API latency monitoring (pause if > 500ms)
- Minimum liquidity filters ($500k daily volume)

---

## 📊 Competition Results

**Competition Period**: Dec 17-20, 2025  
**Starting Capital**: $1,000 USDC  
**Final Balance**: TBD  
**Total ROI**: TBD  

Results will be updated here after the competition concludes.

---

## 🧪 Testing

The bot includes test mode for strategy validation:

```bash
# Run in test mode (paper trading)
python src/main.py --test-mode

# Backtest strategies on historical data
python src/backtest.py --start-date 2025-12-01 --end-date 2025-12-15
```

---

## 📝 License

This project is proprietary and confidential. Built for LunarCrush internal use only.

---

## 👥 Credits

**Developed by**: [Your Name]  
**For**: LunarCrush Trading Competition  
**Date**: December 2025  

**Powered by**:
- [LunarCrush](https://lunarcrush.com) - Social intelligence data
- [Hyperliquid](https://hyperliquid.xyz) - Perpetuals trading
- Python 3.11 + asyncio

---

## 📞 Support

For questions or issues:
- Internal Slack: #trading-bot-support
- Email: [your-email]

---

**⚡ Ready to compete. Let's win this! 🚀**
