# 🦢 BLACK SWAN RADAR

> Global financial anomaly detector — Black Swan events & Dead Cat Bounce patterns.
> Covers crypto (15+ coins) + macro (indices, forex, gold, bonds, VIX).
> 100% free. Hosted on GitHub Pages. Auto-updates every 6 hours via GitHub Actions.

---

## 📁 Repo Structure
black-swan-radar/
├── index.html                  ← Dashboard (GitHub Pages serves this)
├── requirements.txt            ← Python dependencies
├── data/                       ← Auto-generated JSON (committed by GitHub Actions)
│   ├── manifest.json
│   ├── crypto.json
│   ├── macro.json
│   ├── sentiment.json
│   ├── anomalies.json
│   └── dead_cats.json
├── pipeline/
│   ├── fetch_data.py           ← Phase 1: Data fetch
│   ├── analyze.py              ← Phase 2: Isolation Forest scoring
│   └── dead_cat.py             ← Phase 3: DCB pattern engine
└── .github/
└── workflows/
└── update.yml          ← Phase 4: GitHub Actions automation
---

## 🚀 Quick Start

### 1. Enable GitHub Pages
- Go to repo **Settings → Pages**
- Source: **Deploy from branch** → `main` → `/ (root)`
- Save

### 2. GitHub Actions runs automatically
- First run triggers when you push files
- Then every 6 hours thereafter
- Go to **Actions** tab to watch it run

### 3. View your dashboard
After the workflow completes (2-3 min):
https://yourusername.github.io/black-swan-radar/
---

## 📊 What Gets Detected

### Black Swan Signals (Isolation Forest)
- Volume spikes (z-score > 2.5σ)
- Price crashes > 10% in 24h
- Extreme volatility (annualised > 150%)
- Accelerating crash velocity
- Price far below statistical mean
- Cross-asset correlation breakdown

### Dead Cat Bounce Patterns
- Minimum drop ≥ 10% from recent swing high
- Bounce ≥ 3% from trough
- Recovery < 61.8% Fibonacci level
- Confidence: LOW / MEDIUM / HIGH / CONFIRMED
- Re-test confirmation detection
- Momentum divergence (price up, volume down)

---

## 🔧 Data Sources (All Free)

| Source | Data | Key Required? |
|--------|------|--------------|
| CoinGecko API | Crypto prices, OHLCV, ATH | ❌ No |
| yfinance | Stocks, forex, gold, VIX, bonds | ❌ No |
| alternative.me | Fear & Greed Index | ❌ No |

---

## ⚙️ Customisation

### Add more crypto coins
Edit `CRYPTO_IDS` list in `pipeline/fetch_data.py`

### Add more macro assets  
Edit `MACRO_TICKERS` dict in `pipeline/fetch_data.py`

### Change update frequency
Edit the cron in `.github/workflows/update.yml`

---

## ⚠️ Disclaimer

This is an educational tool for pattern detection only.
**NOT financial advice.** Always do your own research.
