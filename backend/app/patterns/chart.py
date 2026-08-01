"""Chart pattern detection using swing highs/lows and geometric heuristics."""
from __future__ import annotations

import numpy as np
import pandas as pd


def find_swings(df: pd.DataFrame, left: int = 3, right: int = 3) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    for i in range(left, n - right):
        if high[i] == max(high[i - left : i + right + 1]):
            highs.append((i, float(high[i])))
        if low[i] == min(low[i - left : i + right + 1]):
            lows.append((i, float(low[i])))
    return highs, lows


def detect_trend(df: pd.DataFrame, lookback: int = 50) -> dict:
    window = df.tail(lookback)
    if len(window) < 10:
        return {"trend": "sideways", "strength": 0.3, "score": 50}
    closes = window["close"].values
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, closes, 1)[0])
    pct = slope / closes.mean() * 100 if closes.mean() else 0
    sma20 = window["close"].rolling(20).mean().iloc[-1] if len(window) >= 20 else closes[-1]
    sma50 = window["close"].rolling(min(50, len(window))).mean().iloc[-1]
    last = closes[-1]
    if pct > 0.05 and last > sma20:
        trend = "uptrend"
        strength = min(1.0, abs(pct) * 5)
    elif pct < -0.05 and last < sma20:
        trend = "downtrend"
        strength = min(1.0, abs(pct) * 5)
    else:
        trend = "sideways"
        strength = 0.4
    score = 50 + pct * 200
    score = max(0, min(100, score))
    return {
        "trend": trend,
        "strength": round(strength, 3),
        "score": round(float(score), 2),
        "slope": round(pct, 5),
        "above_sma20": bool(last > sma20),
        "above_sma50": bool(last > sma50) if not np.isnan(sma50) else None,
    }


def _near_equal(a: float, b: float, tol: float = 0.02) -> bool:
    if a == 0:
        return abs(b) < tol
    return abs(a - b) / abs(a) <= tol


def detect_chart_patterns(df: pd.DataFrame) -> list[dict]:
    if len(df) < 40:
        return []

    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    patterns: list[dict] = []
    highs, lows = find_swings(data, left=4, right=4)
    close = float(data["close"].iloc[-1])
    dates = data.index if isinstance(data.index, pd.DatetimeIndex) else None

    def date_at(idx: int):
        if dates is not None:
            return dates[idx].date() if hasattr(dates[idx], "date") else dates[idx]
        if "date" in data.columns:
            return data["date"].iloc[idx]
        return None

    # Double Top
    if len(highs) >= 2:
        i1, p1 = highs[-2]
        i2, p2 = highs[-1]
        if _near_equal(p1, p2, 0.025) and i2 - i1 >= 5:
            neck = min(data["low"].iloc[i1:i2])
            if close < neck:
                patterns.append(
                    {
                        "pattern_name": "Double Top",
                        "signal": "bearish",
                        "start_date": date_at(i1),
                        "end_date": date_at(i2),
                        "strength": 0.75,
                        "target_price": round(neck - (p1 - neck), 2),
                        "stop_loss": round(max(p1, p2) * 1.01, 2),
                        "meta": {"peaks": [p1, p2], "neckline": float(neck)},
                    }
                )
            else:
                patterns.append(
                    {
                        "pattern_name": "Double Top (forming)",
                        "signal": "bearish",
                        "start_date": date_at(i1),
                        "end_date": date_at(i2),
                        "strength": 0.55,
                        "target_price": None,
                        "stop_loss": None,
                        "meta": {"peaks": [p1, p2], "neckline": float(neck)},
                    }
                )

    # Double Bottom
    if len(lows) >= 2:
        i1, p1 = lows[-2]
        i2, p2 = lows[-1]
        if _near_equal(p1, p2, 0.025) and i2 - i1 >= 5:
            neck = max(data["high"].iloc[i1:i2])
            if close > neck:
                patterns.append(
                    {
                        "pattern_name": "Double Bottom",
                        "signal": "bullish",
                        "start_date": date_at(i1),
                        "end_date": date_at(i2),
                        "strength": 0.75,
                        "target_price": round(neck + (neck - p1), 2),
                        "stop_loss": round(min(p1, p2) * 0.99, 2),
                        "meta": {"troughs": [p1, p2], "neckline": float(neck)},
                    }
                )

    # Triple Top / Bottom
    if len(highs) >= 3:
        pts = highs[-3:]
        if all(_near_equal(pts[0][1], p, 0.03) for _, p in pts[1:]):
            patterns.append(
                {
                    "pattern_name": "Triple Top",
                    "signal": "bearish",
                    "start_date": date_at(pts[0][0]),
                    "end_date": date_at(pts[-1][0]),
                    "strength": 0.8,
                    "target_price": None,
                    "stop_loss": round(max(p for _, p in pts) * 1.01, 2),
                    "meta": {"peaks": [p for _, p in pts]},
                }
            )
    if len(lows) >= 3:
        pts = lows[-3:]
        if all(_near_equal(pts[0][1], p, 0.03) for _, p in pts[1:]):
            patterns.append(
                {
                    "pattern_name": "Triple Bottom",
                    "signal": "bullish",
                    "start_date": date_at(pts[0][0]),
                    "end_date": date_at(pts[-1][0]),
                    "strength": 0.8,
                    "target_price": None,
                    "stop_loss": round(min(p for _, p in pts) * 0.99, 2),
                    "meta": {"troughs": [p for _, p in pts]},
                }
            )

    # Head & Shoulders (approx: 3 highs, middle highest)
    if len(highs) >= 3:
        (li, lp), (mi, mp), (ri, rp) = highs[-3:]
        if mp > lp and mp > rp and _near_equal(lp, rp, 0.04) and ri - li >= 10:
            neck = min(data["low"].iloc[li:ri])
            patterns.append(
                {
                    "pattern_name": "Head & Shoulders",
                    "signal": "bearish",
                    "start_date": date_at(li),
                    "end_date": date_at(ri),
                    "strength": 0.82,
                    "target_price": round(float(neck - (mp - neck)), 2),
                    "stop_loss": round(mp * 1.01, 2),
                    "meta": {"left": lp, "head": mp, "right": rp, "neckline": float(neck)},
                }
            )

    # Inverse H&S
    if len(lows) >= 3:
        (li, lp), (mi, mp), (ri, rp) = lows[-3:]
        if mp < lp and mp < rp and _near_equal(lp, rp, 0.04) and ri - li >= 10:
            neck = max(data["high"].iloc[li:ri])
            patterns.append(
                {
                    "pattern_name": "Inverse Head & Shoulders",
                    "signal": "bullish",
                    "start_date": date_at(li),
                    "end_date": date_at(ri),
                    "strength": 0.82,
                    "target_price": round(float(neck + (neck - mp)), 2),
                    "stop_loss": round(mp * 0.99, 2),
                    "meta": {"left": lp, "head": mp, "right": rp, "neckline": float(neck)},
                }
            )

    # Triangles via recent swing compression
    recent = data.tail(40)
    hh = recent["high"].rolling(5).max()
    ll = recent["low"].rolling(5).min()
    upper_slope = np.polyfit(np.arange(len(hh.dropna())), hh.dropna().values, 1)[0] if hh.dropna().size > 5 else 0
    lower_slope = np.polyfit(np.arange(len(ll.dropna())), ll.dropna().values, 1)[0] if ll.dropna().size > 5 else 0
    range_shrink = (hh.iloc[-1] - ll.iloc[-1]) < (hh.iloc[10] - ll.iloc[10]) * 0.7 if len(hh) > 10 else False

    if range_shrink:
        if upper_slope < -0.01 and abs(lower_slope) < 0.01:
            patterns.append(
                {
                    "pattern_name": "Descending Triangle",
                    "signal": "bearish",
                    "start_date": date_at(max(0, len(data) - 40)),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.65,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"upper_slope": float(upper_slope), "lower_slope": float(lower_slope)},
                }
            )
        elif lower_slope > 0.01 and abs(upper_slope) < 0.01:
            patterns.append(
                {
                    "pattern_name": "Ascending Triangle",
                    "signal": "bullish",
                    "start_date": date_at(max(0, len(data) - 40)),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.65,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"upper_slope": float(upper_slope), "lower_slope": float(lower_slope)},
                }
            )
        elif upper_slope < -0.005 and lower_slope > 0.005:
            patterns.append(
                {
                    "pattern_name": "Symmetrical Triangle",
                    "signal": "neutral",
                    "start_date": date_at(max(0, len(data) - 40)),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.6,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"upper_slope": float(upper_slope), "lower_slope": float(lower_slope)},
                }
            )

    # Rectangle — flat highs and lows
    if len(highs) >= 2 and len(lows) >= 2:
        rh = [p for _, p in highs[-3:]]
        rl = [p for _, p in lows[-3:]]
        if max(rh) - min(rh) < close * 0.02 and max(rl) - min(rl) < close * 0.02:
            patterns.append(
                {
                    "pattern_name": "Rectangle",
                    "signal": "neutral",
                    "start_date": date_at(highs[-3][0] if len(highs) >= 3 else highs[-2][0]),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.55,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"resistance": float(np.mean(rh)), "support": float(np.mean(rl))},
                }
            )

    # Flag / Pennant — sharp move then consolidation
    if len(data) >= 30:
        move = data["close"].iloc[-30] 
        recent_move = (close - float(move)) / float(move) if move else 0
        cons_vol = data["close"].iloc[-10:].std() / close if close else 0
        if abs(recent_move) > 0.08 and cons_vol < 0.015:
            name = "Bull Flag" if recent_move > 0 else "Bear Flag"
            patterns.append(
                {
                    "pattern_name": name,
                    "signal": "bullish" if recent_move > 0 else "bearish",
                    "start_date": date_at(len(data) - 30),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.6,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"impulse_pct": round(recent_move * 100, 2)},
                }
            )

    # Channel
    if len(highs) >= 2 and len(lows) >= 2:
        h_slope = np.polyfit([i for i, _ in highs[-4:]], [p for _, p in highs[-4:]], 1)[0] if len(highs) >= 2 else 0
        l_slope = np.polyfit([i for i, _ in lows[-4:]], [p for _, p in lows[-4:]], 1)[0] if len(lows) >= 2 else 0
        if abs(h_slope - l_slope) < abs(close) * 0.001 and abs(h_slope) > 0:
            patterns.append(
                {
                    "pattern_name": "Channel",
                    "signal": "bullish" if h_slope > 0 else "bearish",
                    "start_date": date_at(min(highs[-2][0], lows[-2][0])),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.58,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {"slope": float(h_slope)},
                }
            )

    # Cup & Handle (simplified U-shape + small dip)
    if len(data) >= 60:
        seg = data.tail(60)["close"].values
        left_peak = float(np.max(seg[:15]))
        bottom = float(np.min(seg[15:40]))
        right = float(np.max(seg[40:50]))
        handle = float(np.min(seg[50:]))
        if (
            _near_equal(left_peak, right, 0.05)
            and bottom < left_peak * 0.9
            and handle < right * 0.98
            and handle > bottom
        ):
            patterns.append(
                {
                    "pattern_name": "Cup & Handle",
                    "signal": "bullish",
                    "start_date": date_at(len(data) - 60),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.7,
                    "target_price": round(right + (right - bottom), 2),
                    "stop_loss": round(handle * 0.98, 2),
                    "meta": {"cup_bottom": bottom, "rim": right},
                }
            )

    # Rounding Bottom
    if len(data) >= 40:
        seg = data.tail(40)["close"].values
        mid = len(seg) // 2
        if seg[mid] < seg[0] * 0.95 and seg[-1] > seg[mid] * 1.03 and abs(seg[-1] - seg[0]) / seg[0] < 0.08:
            patterns.append(
                {
                    "pattern_name": "Rounding Bottom",
                    "signal": "bullish",
                    "start_date": date_at(len(data) - 40),
                    "end_date": date_at(len(data) - 1),
                    "strength": 0.62,
                    "target_price": None,
                    "stop_loss": None,
                    "meta": {},
                }
            )

    # Breakout / Breakdown vs recent range
    look = data.tail(20)
    resist = float(look["high"].iloc[:-1].max())
    support = float(look["low"].iloc[:-1].min())
    vol_avg = float(look["volume"].iloc[:-1].mean()) if "volume" in look else 0
    last_vol = float(data["volume"].iloc[-1]) if "volume" in data else 0
    if close > resist * 1.005 and (vol_avg == 0 or last_vol > vol_avg * 1.2):
        patterns.append(
            {
                "pattern_name": "Breakout",
                "signal": "bullish",
                "start_date": date_at(len(data) - 20),
                "end_date": date_at(len(data) - 1),
                "strength": 0.78,
                "target_price": round(close + (resist - support), 2),
                "stop_loss": round(resist * 0.99, 2),
                "meta": {"level": resist},
            }
        )
    if close < support * 0.995 and (vol_avg == 0 or last_vol > vol_avg * 1.2):
        patterns.append(
            {
                "pattern_name": "Breakdown",
                "signal": "bearish",
                "start_date": date_at(len(data) - 20),
                "end_date": date_at(len(data) - 1),
                "strength": 0.78,
                "target_price": round(close - (resist - support), 2),
                "stop_loss": round(support * 1.01, 2),
                "meta": {"level": support},
            }
        )

    # Wedge
    if upper_slope < -0.01 and lower_slope < -0.005 and upper_slope < lower_slope:
        patterns.append(
            {
                "pattern_name": "Falling Wedge",
                "signal": "bullish",
                "start_date": date_at(max(0, len(data) - 40)),
                "end_date": date_at(len(data) - 1),
                "strength": 0.6,
                "target_price": None,
                "stop_loss": None,
                "meta": {},
            }
        )
    if upper_slope > 0.005 and lower_slope > 0.01 and upper_slope < lower_slope:
        patterns.append(
            {
                "pattern_name": "Rising Wedge",
                "signal": "bearish",
                "start_date": date_at(max(0, len(data) - 40)),
                "end_date": date_at(len(data) - 1),
                "strength": 0.6,
                "target_price": None,
                "stop_loss": None,
                "meta": {},
            }
        )

    # Pennant
    if range_shrink and abs(upper_slope) > 0.005 and abs(lower_slope) > 0.005 and upper_slope * lower_slope < 0:
        patterns.append(
            {
                "pattern_name": "Pennant",
                "signal": "neutral",
                "start_date": date_at(max(0, len(data) - 25)),
                "end_date": date_at(len(data) - 1),
                "strength": 0.55,
                "target_price": None,
                "stop_loss": None,
                "meta": {},
            }
        )

    return patterns
