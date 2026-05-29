"""
BLACK SWAN RADAR — Phase 1: Data Pipeline
==========================================
Fetches crypto (CoinGecko), macro assets (yfinance),
sentiment (Fear & Greed), and outputs clean JSON files.

Run: python fetch_data.py
Output: ../data/crypto.json, ../data/macro.json, ../data/sentiment.json
"""

import requests
import json
import os
import time
from datetime import datetime, timezone

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved → {path}")


# CRYPTO DATA
CRYPTO_IDS = [
    "bitcoin", "ethereum", "solana", "binancecoin",
    "ripple", "cardano", "dogecoin", "avalanche-2",
    "chainlink", "polkadot", "toncoin", "shiba-inu",
    "matic-network", "uniswap", "pepe"
]

def fetch_crypto_prices():
    print("\n[1/4] Fetching crypto prices from CoinGecko...")
    ids = ",".join(CRYPTO_IDS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}"
        "&order=market_cap_desc&per_page=50&page=1"
        "&sparkline=false&price_change_percentage=1h,24h,7d,30d"
    )

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        coins = r.json()

        result = []
        for c in coins:
            result.append({
                "id": c.get("id"),
                "symbol": c.get("symbol", "").upper(),
                "name": c.get("name"),
                "price_usd": c.get("current_price"),
                "market_cap": c.get("market_cap"),
                "volume_24h": c.get("total_volume"),
                "change_1h_pct": c.get("price_change_percentage_1h_in_currency"),
                "change_24h_pct": c.get("price_change_percentage_24h_in_currency"),
                "change_7d_pct": c.get("price_change_percentage_7d_in_currency"),
                "change_30d_pct": c.get("price_change_percentage_30d_in_currency"),
                "ath": c.get("ath"),
                "ath_change_pct": c.get("ath_change_percentage"),
                "ath_date": c.get("ath_date"),
                "market_cap_rank": c.get("market_cap_rank"),
                "last_updated": c.get("last_updated"),
            })

        print(f"  → Fetched {len(result)} coins")
        return result

    except Exception as e:
        print(f"  ❌ CoinGecko error: {e}")
        return []


def fetch_crypto_history(coin_id, days=90):
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        f"?vs_currency=usd&days={days}"
    )
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        raw = r.json()
        return [
            {
                "ts": entry[0],
                "open": entry[1],
                "high": entry[2],
                "low": entry[3],
                "close": entry[4],
            }
            for entry in raw
        ]
    except Exception as e:
        print(f"    ⚠ History fetch failed for {coin_id}: {e}")
        return []


def fetch_all_crypto_history():
    print("\n[2/4] Fetching crypto price history (90d OHLCV)...")
    priority = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
    history = {}
    for coin_id in priority:
        print(f"  → {coin_id}...", end=" ")
        history[coin_id] = fetch_crypto_history(coin_id, days=90)
        print(f"{len(history[coin_id])} candles")
        time.sleep(1.2)
    return history


# MACRO DATA
MACRO_TICKERS = {
    "^GSPC":  {"name": "S&P 500",       "category": "index"},
    "^IXIC":  {"name": "NASDAQ",         "category": "index"},
    "^DJI":   {"name": "Dow Jones",      "category": "index"},
    "^VIX":   {"name": "VIX Fear Index", "category": "volatility"},
    "GC=F":   {"name": "Gold",           "category": "commodity"},
    "SI=F":   {"name": "Silver",         "category": "commodity"},
    "CL=F":   {"name": "Crude Oil",      "category": "commodity"},
    "DX-Y.NYB": {"name": "DXY (USD Index)", "category": "forex"},
    "EURUSD=X": {"name": "EUR/USD",      "category": "forex"},
    "^TNX":   {"name": "10Y Treasury Yield", "category": "bond"},
    "^TYX":   {"name": "30Y Treasury Yield", "category": "bond"},
    "IBIT":   {"name": "Bitcoin ETF (IBIT)", "category": "etf"},
    "ETHA":   {"name": "Ethereum ETF (ETHA)","category": "etf"},
}

def fetch_macro_data():
    print("\n[3/4] Fetching macro data via yfinance...")

    try:
        import yfinance as yf
    except ImportError:
        print("  ❌ yfinance not installed.")
        return {}

    result = {}
    for ticker, meta in MACRO_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="90d", interval="1d")

            if hist.empty:
                print(f"  ⚠ No data for {ticker}")
                continue

            latest = hist.iloc[-1]
            prev   = hist.iloc[-2] if len(hist) > 1 else latest
            change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100

            recent_30 = hist.tail(30)
            high_30 = float(recent_30["High"].max())
            low_30  = float(recent_30["Low"].min())

            history = []
            for dt, row in hist.iterrows():
                history.append({
                    "date": str(dt.date()),
                    "open":   round(float(row["Open"]),   4),
                    "high":   round(float(row["High"]),   4),
                    "low":    round(float(row["Low"]),    4),
                    "close":  round(float(row["Close"]),  4),
                    "volume": int(row["Volume"]) if row["Volume"] else 0,
                })

            result[ticker] = {
                **meta,
                "ticker": ticker,
                "price":       round(float(latest["Close"]), 4),
                "change_24h_pct": round(float(change_pct), 2),
                "high_30d":    round(high_30, 4),
                "low_30d":     round(low_30,  4),
                "drawdown_from_30d_high_pct": round(
                    ((float(latest["Close"]) - high_30) / high_30) * 100, 2
                ),
                "history": history,
            }
            print(f"  ✅ {meta['name']}: ${result[ticker]['price']:,.4f}")

        except Exception as e:
            print(f"  ❌ {ticker} failed: {e}")

    return result


# SENTIMENT
def fetch_fear_greed():
    print("\n[4/4] Fetching Fear & Greed Index...")
    url = "https://api.alternative.me/fng/?limit=30&format=json"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()["data"]

        history = [
            {
                "date": datetime.fromtimestamp(
                    int(entry["timestamp"]), tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "value": int(entry["value"]),
                "label": entry["value_classification"],
            }
            for entry in data
        ]

        current = history[0] if history else {}
        print(f"  → Current: {current.get('value')} — {current.get('label')}")

        return {
            "current": current,
            "history_30d": history,
        }

    except Exception as e:
        print(f"  ❌ Fear & Greed error: {e}")
        return {}


# MAIN
def main():
    print("=" * 60)
    print("  BLACK SWAN RADAR — Data Pipeline")
    print(f"  Run time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    timestamp = datetime.now(timezone.utc).isoformat()

    crypto_prices  = fetch_crypto_prices()
    time.sleep(2)
    crypto_history = fetch_all_crypto_history()

    crypto_output = {
        "fetched_at": timestamp,
        "prices": crypto_prices,
        "history": crypto_history,
    }
    save_json("crypto.json", crypto_output)

    macro_data = fetch_macro_data()
    macro_output = {
        "fetched_at": timestamp,
        "assets": macro_data,
    }
    save_json("macro.json", macro_output)

    sentiment = fetch_fear_greed()
    sentiment["fetched_at"] = timestamp
    save_json("sentiment.json", sentiment)

    manifest = {
        "last_updated": timestamp,
        "crypto_count": len(crypto_prices),
        "macro_count": len(macro_data),
        "fear_greed": sentiment.get("current", {}),
        "files": ["crypto.json", "macro.json", "sentiment.json"],
    }
    save_json("manifest.json", manifest)

    print("\n" + "=" * 60)
    print("  ✅ Phase 1 complete. All data saved to /data/")
    print("=" * 60)


if __name__ == "__main__":
    main()
