"""
BLACK SWAN RADAR — Phase 2: Feature Engineering + Anomaly Detection
Reads data/*.json → engineers features → runs Isolation Forest
"""

import json
import os
import math
import numpy as np
from datetime import datetime, timezone

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
CRYPTO_F   = os.path.join(BASE_DIR, "crypto.json")
MACRO_F    = os.path.join(BASE_DIR, "macro.json")
SENTIMENT_F= os.path.join(BASE_DIR, "sentiment.json")
OUT_FILE   = os.path.join(BASE_DIR, "anomalies.json")

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved → {path}")


def safe(val, default=0.0):
    if val is None:
        return default
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return default


def compute_zscore(series):
    if len(series) < 3:
        return 0.0
    arr = np.array(series, dtype=float)
    mean = np.mean(arr[:-1])
    std  = np.std(arr[:-1])
    if std == 0:
        return 0.0
    return float((arr[-1] - mean) / std)


def rolling_volatility(closes, window=14):
    if len(closes) < window + 1:
        return 0.0
    arr = np.array(closes[-(window + 1):], dtype=float)
    returns = np.diff(arr) / arr[:-1]
    return float(np.std(returns) * math.sqrt(365))


def max_drawdown(closes):
    if len(closes) < 2:
        return 0.0
    arr = np.array(closes, dtype=float)
    peak = arr[0]
    max_dd = 0.0
    for v in arr:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return float(max_dd)


def extract_crypto_features(coin, history_list):
    closes  = [c["close"] for c in history_list] if history_list else []
    volumes = [c.get("volume", 0) or 0 for c in history_list] if history_list else []

    chg_1h  = safe(coin.get("change_1h_pct"))
    chg_24h = safe(coin.get("change_24h_pct"))
    chg_7d  = safe(coin.get("change_7d_pct"))
    chg_30d = safe(coin.get("change_30d_pct"))

    ath_dd  = safe(coin.get("ath_change_pct"))

    vol_zscore = compute_zscore(volumes) if len(volumes) > 5 else 0.0
    price_zscore = compute_zscore(closes) if len(closes) > 5 else 0.0

    volatility = rolling_volatility(closes, window=14)
    max_dd = max_drawdown(closes) * 100

    velocity = 0.0
    if chg_30d != 0:
        velocity = chg_7d / (abs(chg_30d) + 1e-9)

    return {
        "change_1h_pct":    chg_1h,
        "change_24h_pct":   chg_24h,
        "change_7d_pct":    chg_7d,
        "change_30d_pct":   chg_30d,
        "ath_drawdown_pct": ath_dd,
        "volume_zscore":    round(vol_zscore, 3),
        "price_zscore":     round(price_zscore, 3),
        "volatility_ann":   round(volatility, 4),
        "max_drawdown_pct": round(max_dd, 2),
        "crash_velocity":   round(velocity, 4),
    }


def extract_macro_features(asset):
    chg_24h = safe(asset.get("change_24h_pct"))
    dd_30d  = safe(asset.get("drawdown_from_30d_high_pct"))

    history = asset.get("history", [])
    closes  = [h["close"] for h in history]
    volumes = [h.get("volume", 0) or 0 for h in history]

    vol_zscore   = compute_zscore(volumes) if len(volumes) > 5 else 0.0
    price_zscore = compute_zscore(closes)  if len(closes) > 5  else 0.0
    volatility   = rolling_volatility(closes, window=14)
    max_dd       = max_drawdown(closes) * 100

    return {
        "change_24h_pct":             chg_24h,
        "drawdown_from_30d_high_pct": dd_30d,
        "volume_zscore":              round(vol_zscore, 3),
        "price_zscore":               round(price_zscore, 3),
        "volatility_ann":             round(volatility, 4),
        "max_drawdown_pct":           round(max_dd, 2),
        "change_1h_pct":              0.0,
        "change_7d_pct":              0.0,
        "change_30d_pct":             0.0,
        "ath_drawdown_pct":           0.0,
        "crash_velocity":             0.0,
    }


FEATURE_KEYS = [
    "change_1h_pct",
    "change_24h_pct",
    "change_7d_pct",
    "change_30d_pct",
    "ath_drawdown_pct",
    "volume_zscore",
    "price_zscore",
    "volatility_ann",
    "max_drawdown_pct",
    "crash_velocity",
]

def run_isolation_forest(feature_dicts):
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import RobustScaler
    except ImportError:
        print("  ❌ scikit-learn not found.")
        return [50.0] * len(feature_dicts)

    X = np.array([
        [safe(fd.get(k)) for k in FEATURE_KEYS]
        for fd in feature_dicts
    ])

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    clf = IsolationForest(
        n_estimators=200,
        contamination=0.1,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_scaled)

    raw_scores = clf.decision_function(X_scaled)

    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s == min_s:
        return [50.0] * len(feature_dicts)

    normalised = 100.0 * (1.0 - (raw_scores - min_s) / (max_s - min_s))
    return [round(float(s), 1) for s in normalised]


def risk_label(score):
    if score >= 80:  return "🔴 CRITICAL"
    if score >= 65:  return "🟠 HIGH"
    if score >= 45:  return "🟡 ELEVATED"
    if score >= 25:  return "🟢 NORMAL"
    return               "🔵 CALM"


def build_signal_flags(features, asset_type="crypto"):
    flags = []

    if features.get("volume_zscore", 0) > 2.5:
        flags.append("📊 Volume spike ({}σ)".format(round(features["volume_zscore"], 1)))

    if features.get("change_24h_pct", 0) < -10:
        flags.append("📉 24h crash >10%")
    elif features.get("change_24h_pct", 0) > 15:
        flags.append("📈 24h pump >15%")

    if features.get("change_7d_pct", 0) < -25:
        flags.append("🩸 7d drawdown >25%")

    if features.get("volatility_ann", 0) > 1.5:
        flags.append("⚡ Extreme volatility")

    if features.get("crash_velocity", 0) < -0.5:
        flags.append("🌀 Crash accelerating")

    if features.get("ath_drawdown_pct", 0) < -70:
        flags.append("🪦 >70% below ATH")

    if features.get("price_zscore", 0) < -2.5:
        flags.append("🔻 Price far below mean")
    elif features.get("price_zscore", 0) > 2.5:
        flags.append("🔺 Price far above mean")

    if features.get("drawdown_from_30d_high_pct", 0) < -15:
        flags.append("📉 >15% off 30d high")

    return flags


def main():
    print("=" * 60)
    print("  BLACK SWAN RADAR — Phase 2: Anomaly Detection")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    print("\n📂 Loading data files...")
    try:
        crypto_data   = load_json(CRYPTO_F)
        macro_data    = load_json(MACRO_F)
        sentiment_data= load_json(SENTIMENT_F)
    except FileNotFoundError as e:
        print(f"  ❌ Missing file: {e}")
        return

    crypto_prices  = crypto_data.get("prices", [])
    crypto_history = crypto_data.get("history", {})
    macro_assets   = macro_data.get("assets", {})

    print("\n🔬 Engineering features...")
    all_items = []

    for coin in crypto_prices:
        cid = coin.get("id", "")
        hist = crypto_history.get(cid, [])
        features = extract_crypto_features(coin, hist)
        all_items.append({
            "id":       cid,
            "symbol":   coin.get("symbol", "").upper(),
            "name":     coin.get("name", cid),
            "type":     "crypto",
            "price":    coin.get("price_usd"),
            "market_cap": coin.get("market_cap"),
            "volume_24h": coin.get("volume_24h"),
            "features": features,
        })

    for ticker, asset in macro_assets.items():
        features = extract_macro_features(asset)
        all_items.append({
            "id":       ticker,
            "symbol":   ticker,
            "name":     asset.get("name", ticker),
            "type":     asset.get("category", "macro"),
            "price":    asset.get("price"),
            "features": features,
        })

    print(f"  → {len(all_items)} assets prepared")

    print("\n🌲 Running Isolation Forest...")
    feature_dicts = [item["features"] for item in all_items]
    scores        = run_isolation_forest(feature_dicts)

    results = []
    for item, score in zip(all_items, scores):
        flags = build_signal_flags(item["features"], item["type"])
        results.append({
            **item,
            "anomaly_score":  score,
            "risk_level":     risk_label(score),
            "signal_flags":   flags,
        })

    results.sort(key=lambda x: x["anomaly_score"], reverse=True)

    crypto_scores = [r["anomaly_score"] for r in results if r["type"] == "crypto"]
    macro_scores  = [r["anomaly_score"] for r in results if r["type"] != "crypto"]
    fg_value      = sentiment_data.get("current", {}).get("value", 50)

    global_score = round(
        (
            (np.mean(crypto_scores) * 0.5 if crypto_scores else 0) +
            (np.mean(macro_scores)  * 0.3 if macro_scores  else 0) +
            ((100 - int(fg_value))  * 0.2)
        ), 1
    )

    top_alerts = [
        {
            "id":    r["id"],
            "name":  r["name"],
            "score": r["anomaly_score"],
            "risk":  r["risk_level"],
            "flags": r["signal_flags"],
        }
        for r in results[:5]
    ]

    output = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "global_risk_score": global_score,
        "global_risk_level": risk_label(global_score),
        "fear_greed_value":  int(fg_value),
        "top_alerts":        top_alerts,
        "assets":            results,
    }

    save_json(OUT_FILE, output)

    print(f"\n{'═'*60}")
    print(f"  🌍 GLOBAL RISK SCORE: {global_score}/100 — {risk_label(global_score)}")
    print(f"  😱 Fear & Greed: {fg_value}")
    print(f"\n  🚨 TOP ALERTS:")
    for a in top_alerts:
        print(f"    [{a['score']:5.1f}] {a['name']:<25} {a['risk']}")
        for flag in a["flags"]:
            print(f"            {flag}")
    print(f"{'═'*60}")
    print("  ✅ Phase 2 complete → data/anomalies.json")


if __name__ == "__main__":
    main()
