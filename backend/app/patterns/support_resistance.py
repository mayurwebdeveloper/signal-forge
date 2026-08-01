"""Support & Resistance engine."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from app.patterns.chart import find_swings


def cluster_levels(levels: list[float], tolerance: float = 0.015) -> list[dict]:
    if not levels:
        return []
    levels = sorted(levels)
    clusters: list[list[float]] = [[levels[0]]]
    for lvl in levels[1:]:
        if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] <= tolerance:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])
    result = []
    for cluster in clusters:
        price = float(np.mean(cluster))
        result.append({"price": round(price, 4), "touches": len(cluster), "strength": min(1.0, 0.4 + 0.15 * len(cluster))})
    return result


def calculate_support_resistance(df: pd.DataFrame) -> list[dict]:
    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    if len(data) < 20:
        return []

    close = float(data["close"].iloc[-1])
    highs, lows = find_swings(data, left=3, right=3)
    swing_high_prices = [p for _, p in highs]
    swing_low_prices = [p for _, p in lows]

    results: list[dict] = []

    for cluster in cluster_levels(swing_high_prices):
        results.append(
            {
                "level_type": "resistance" if cluster["price"] >= close else "support",
                "price": cluster["price"],
                "strength": cluster["strength"],
                "touches": cluster["touches"],
                "date": None,
                "meta": {"source": "swing_cluster"},
            }
        )

    for cluster in cluster_levels(swing_low_prices):
        results.append(
            {
                "level_type": "support" if cluster["price"] <= close else "resistance",
                "price": cluster["price"],
                "strength": cluster["strength"],
                "touches": cluster["touches"],
                "date": None,
                "meta": {"source": "swing_cluster"},
            }
        )

    # Classic pivots from last bar
    last = data.iloc[-2] if len(data) > 1 else data.iloc[-1]
    pivot = (float(last["high"]) + float(last["low"]) + float(last["close"])) / 3
    r1 = 2 * pivot - float(last["low"])
    s1 = 2 * pivot - float(last["high"])
    r2 = pivot + (float(last["high"]) - float(last["low"]))
    s2 = pivot - (float(last["high"]) - float(last["low"]))
    for level_type, price in [
        ("pivot", pivot),
        ("resistance", r1),
        ("resistance", r2),
        ("support", s1),
        ("support", s2),
    ]:
        results.append(
            {
                "level_type": level_type,
                "price": round(price, 4),
                "strength": 0.6,
                "touches": 1,
                "date": None,
                "meta": {"source": "pivot"},
            }
        )

    # Recent swing high/low markers
    if highs:
        idx, price = highs[-1]
        results.append(
            {
                "level_type": "swing_high",
                "price": round(price, 4),
                "strength": 0.7,
                "touches": 1,
                "date": None,
                "meta": {"index": idx},
            }
        )
    if lows:
        idx, price = lows[-1]
        results.append(
            {
                "level_type": "swing_low",
                "price": round(price, 4),
                "strength": 0.7,
                "touches": 1,
                "date": None,
                "meta": {"index": idx},
            }
        )

    # Deduplicate near levels
    results.sort(key=lambda x: (x["level_type"], x["price"]))
    deduped: list[dict] = []
    for r in results:
        if deduped and deduped[-1]["level_type"] == r["level_type"] and abs(deduped[-1]["price"] - r["price"]) / r["price"] < 0.008:
            if r["strength"] > deduped[-1]["strength"]:
                deduped[-1] = r
            continue
        deduped.append(r)

    # Sort by distance from price
    for r in deduped:
        r["distance_pct"] = round(abs(r["price"] - close) / close * 100, 3) if close else 0
    deduped.sort(key=lambda x: x["distance_pct"])
    return deduped[:25]


def nearest_levels(levels: list[dict], price: float) -> dict:
    supports = [l for l in levels if l["level_type"] in ("support", "swing_low", "pivot") and l["price"] <= price]
    resistances = [l for l in levels if l["level_type"] in ("resistance", "swing_high") and l["price"] >= price]
    nearest_support = max(supports, key=lambda x: x["price"]) if supports else None
    nearest_resistance = min(resistances, key=lambda x: x["price"]) if resistances else None
    return {
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "support_distance_pct": round((price - nearest_support["price"]) / price * 100, 3) if nearest_support else None,
        "resistance_distance_pct": round((nearest_resistance["price"] - price) / price * 100, 3) if nearest_resistance else None,
    }
