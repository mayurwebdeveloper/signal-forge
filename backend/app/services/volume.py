"""Volume analytics."""
from __future__ import annotations

import numpy as np
import pandas as pd


def analyze_volume(df: pd.DataFrame, lookback: int = 20) -> dict:
    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    if len(data) < lookback + 1 or "volume" not in data.columns:
        return {
            "average_volume": 0,
            "current_volume": 0,
            "volume_spike": False,
            "volume_ratio": 0,
            "buying_pressure": 0.5,
            "selling_pressure": 0.5,
            "breakout_confirmation": False,
        }

    vol = data["volume"]
    avg = float(vol.iloc[-lookback - 1 : -1].mean())
    current = float(vol.iloc[-1])
    ratio = current / avg if avg else 0
    spike = ratio >= 1.8

    # Buying/selling pressure via up/down volume
    window = data.tail(lookback)
    up_vol = float(window.loc[window["close"] >= window["open"], "volume"].sum())
    down_vol = float(window.loc[window["close"] < window["open"], "volume"].sum())
    total = up_vol + down_vol or 1.0
    buying = up_vol / total
    selling = down_vol / total

    # Breakout confirmation: price near 20d high + volume spike
    recent_high = float(data["high"].iloc[-lookback - 1 : -1].max())
    close = float(data["close"].iloc[-1])
    breakout_conf = spike and close >= recent_high * 0.995

    # OBV trend
    direction = np.sign(data["close"].diff()).fillna(0)
    obv = (direction * data["volume"]).cumsum()
    obv_slope = float(np.polyfit(np.arange(lookback), obv.tail(lookback).values, 1)[0]) if len(obv) >= lookback else 0

    return {
        "average_volume": round(avg, 2),
        "current_volume": round(current, 2),
        "volume_spike": spike,
        "volume_ratio": round(ratio, 3),
        "buying_pressure": round(buying, 3),
        "selling_pressure": round(selling, 3),
        "breakout_confirmation": breakout_conf,
        "obv_slope": round(obv_slope, 2),
        "volume_score": round(min(100, max(0, 50 + (ratio - 1) * 25 + (buying - 0.5) * 40)), 2),
    }
