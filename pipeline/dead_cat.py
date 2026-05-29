"""
BLACK SWAN RADAR — Phase 3: Dead Cat Bounce Engine
Pattern rules for detecting Dead Cat Bounce setups
"""

import json
import os
import math
from datetime import datetime, timezone

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
CRYPTO_F   = os.path.join(BASE_DIR, "crypto.json")
MACRO_F    = os.path.join(BASE_DIR, "macro.json")
OUT_FILE   = os.path.join(BASE_DIR, "dead_cats.json")

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved → {path}")


def safe(v, default=0.0):
    if v is None: return default
    try:
        x = float(v)
        return default if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return default


def find_swing_high(closes, lookback=30):
    window = closes[-lookback:] if len(closes) >= lookback else closes
    offset = max(0, len(closes) - lookback)
    idx    = int(max(range(len(window)), key=lambda i: window[i]))
    return offset + idx, window[idx]


def find_swing_low(closes, start_idx):
    window = closes[start_idx:]
    if not window:
        return start_idx, closes[start_idx] if start_idx < len(closes) else 0
    idx = int(min(range(len(window)), key=lambda i: window[i]))
    return start_idx + idx, window[idx]


def fibonacci_levels(swing_high, swing_low):
    diff = swing_high - swing_low
    return {
        "0.0":   swing_low,
        "23.6":  swing_low + 0.236 * diff,
        "38.2":  swing_low + 0.382 * diff,
        "50.0":  swing_low + 0.500 * diff,
        "61.8":  swing_low + 0.618 * diff,
        "78.6":  swing_low + 0.786 * diff,
        "100.0": swing_high,
    }


def detect_dead_cat(closes, asset_id=""):
    if len(closes) < 20:
        return None

    sh_idx, sh_val = find_swing_high(closes, lookback=60)

    if sh_idx >= len(closes) - 3:
        return None

    trough_idx, trough_val = find_swing_low(closes, sh_idx)

    drop_pct = ((trough_val - sh_val) / sh_val) * 100

    if drop_pct > -10:
        return None

    post_trough = closes[trough_idx:]
    if len(post_trough) < 2:
        return None

    current_price = closes[-1]
    bounce_pct = ((current_price - trough_val) / trough_val) * 100

    if bounce_pct < 3.0:
        return None

    recovery_ratio = bounce_pct / abs(drop_pct)

    fibs = fibonacci_levels(sh_val, trough_val)
    current_fib_pct = None

    for level, fib_price in sorted(fibs.items(), key=lambda x: float(x[0])):
        if abs(current_price - fib_price) / sh_val < 0.02:
            current_fib_pct = float(level)
            break

    is_dcb = (
        bounce_pct >= 3.0 and
        recovery_ratio < 0.618 and
        current_price < sh_val * 0.97
    )

    if is_dcb:
        if recovery_ratio < 0.382:
            dcb_confidence = "HIGH"
        elif recovery_ratio < 0.50:
            dcb_confidence = "MEDIUM"
        else:
            dcb_confidence = "LOW"
    else:
        dcb_confidence = None

    retest_detected = False
    if len(post_trough) > 5:
        post_bounce_lows = post_trough[3:]
        if post_bounce_lows:
            min_after_bounce = min(post_bounce_lows)
            if min_after_bounce <= trough_val * 1.05:
                retest_detected = True
                if is_dcb:
                    dcb_confidence = "CONFIRMED"

    return {
        "detected":         is_dcb,
        "confidence":       dcb_confidence,
        "retest_confirmed": retest_detected,
        "swing_high":       round(sh_val, 6),
        "swing_high_candle":sh_idx,
        "trough":           round(trough_val, 6),
        "trough_candle":    trough_idx,
        "current_price":    round(current_price, 6),
        "drop_pct":         round(drop_pct, 2),
        "bounce_pct":       round(bounce_pct, 2),
        "recovery_ratio":   round(recovery_ratio, 3),
        "fib_levels":       {k: round(v, 6) for k, v in fibs.items()},
        "price_at_fib_pct": current_fib_pct,
        "candles_analysed": len(closes),
    }


def detect_momentum_exhaustion(closes, volumes=None):
    if len(closes) < 10:
        return False, 0.0

    price_trend  = closes[-1] - closes[-10]
    price_rising = price_trend > 0

    if volumes and len(volumes) >= 10:
        vol_recent = sum(volumes[-5:]) / 5
        vol_prior  = sum(volumes[-10:-5]) / 5
        vol_declining = vol_recent < vol_prior * 0.85
    else:
        vol_declining = False

    divergence_score = 0.0
    if price_rising and vol_declining:
        divergence_score = (
            (price_trend / closes[-10]) * 100 *
            (1 - vol_recent / (vol_prior + 1e-9))
        )

    return (price_rising and vol_declining), round(abs(divergence_score), 2)


def process_crypto(crypto_data):
    results = []
    prices  = crypto_data.get("prices", [])
    history = crypto_data.get("history", {})

    for coin in prices:
        cid   = coin.get("id", "")
        hist  = history.get(cid, [])
        closes  = [c["close"]  for c in hist]
        volumes = [c.get("volume", 0) or 0 for c in hist]

        dcb = detect_dead_cat(closes, cid)
        mom_div, div_score = detect_momentum_exhaustion(closes, volumes)

        results.append({
            "id":     cid,
            "symbol": coin.get("symbol", "").upper(),
            "name":   coin.get("name", cid),
            "type":   "crypto",
            "price":  coin.get("price_usd"),
            "dcb":    dcb,
            "momentum_divergence": mom_div,
            "divergence_score":    div_score,
        })

    return results


def process_macro(macro_data):
    results = []
    for ticker, asset in macro_data.get("assets", {}).items():
        hist    = asset.get("history", [])
        closes  = [h["close"]  for h in hist]
        volumes = [h.get("volume", 0) or 0 for h in hist]

        dcb = detect_dead_cat(closes, ticker)
        mom_div, div_score = detect_momentum_exhaustion(closes, volumes)

        results.append({
            "id":     ticker,
            "symbol": ticker,
            "name":   asset.get("name", ticker),
            "type":   asset.get("category", "macro"),
            "price":  asset.get("price"),
            "dcb":    dcb,
            "momentum_divergence": mom_div,
            "divergence_score":    div_score,
        })

    return results


def main():
    print("=" * 60)
    print("  BLACK SWAN RADAR — Phase 3: Dead Cat Bounce Engine")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    try:
        crypto_data = load_json(CRYPTO_F)
        macro_data  = load_json(MACRO_F)
    except FileNotFoundError as e:
        print(f"  ❌ Missing: {e}")
        return

    print("\n🔍 Scanning for Dead Cat Bounce patterns...")
    all_results = process_crypto(crypto_data) + process_macro(macro_data)

    detected = [
        r for r in all_results
        if r.get("dcb") and r["dcb"].get("detected")
    ]
    detected.sort(
        key=lambda x: (
            {"CONFIRMED": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                x["dcb"].get("confidence", ""), 0
            )
        ),
        reverse=True,
    )

    print(f"\n  Found {len(detected)} potential Dead Cat Bounce(s) "
          f"out of {len(all_results)} assets\n")

    for d in detected:
        dcb = d["dcb"]
        print(f"  🐱 {d['name']:<25} Confidence: {dcb['confidence']}")
        print(f"       Drop: {dcb['drop_pct']:+.1f}%  "
              f"Bounce: {dcb['bounce_pct']:+.1f}%  "
              f"Recovery: {dcb['recovery_ratio']*100:.0f}% of drop")
        if d["momentum_divergence"]:
            print(f"       ⚠ Momentum divergence score: {d['divergence_score']}")

    output = {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "total_scanned":   len(all_results),
        "dcb_count":       len(detected),
        "detected":        detected,
        "all_results":     all_results,
    }

    save_json(OUT_FILE, output)
    print("\n  ✅ Phase 3 complete → data/dead_cats.json")


if __name__ == "__main__":
    main()
