"""Candlestick pattern recognition."""
from __future__ import annotations

import pandas as pd


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-9)


def _upper_shadow(o: float, h: float, c: float) -> float:
    return h - max(o, c)


def _lower_shadow(o: float, l: float, c: float) -> float:
    return min(o, c) - l


def detect_candlestick_patterns(df: pd.DataFrame) -> list[dict]:
    """Detect candlestick patterns on the last few bars. Returns list of pattern dicts."""
    if len(df) < 5:
        return []

    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    patterns: list[dict] = []

    i = len(data) - 1
    o, h, l, c = float(data["open"].iloc[i]), float(data["high"].iloc[i]), float(data["low"].iloc[i]), float(data["close"].iloc[i])
    body = _body(o, c)
    rng = _range(h, l)
    us = _upper_shadow(o, h, c)
    ls = _lower_shadow(o, l, c)
    avg_body = data["close"].iloc[-15:-1].sub(data["open"].iloc[-15:-1]).abs().mean() if len(data) > 15 else body
    bullish = c > o
    date_val = data.index[i] if hasattr(data.index[i], "date") else data.iloc[i].get("date")

    def add(name: str, signal: str, strength: float, desc: str):
        patterns.append(
            {
                "date": date_val,
                "pattern_name": name,
                "signal": signal,
                "strength": round(strength, 3),
                "description": desc,
            }
        )

    # Doji
    if body / rng < 0.1:
        add("Doji", "neutral", 0.6, "Indecision — open and close nearly equal")

    # Spinning Top
    if 0.1 <= body / rng <= 0.3 and us > body * 0.5 and ls > body * 0.5:
        add("Spinning Top", "neutral", 0.5, "Indecision with upper and lower shadows")

    # Marubozu
    if body / rng > 0.9:
        add("Marubozu", "bullish" if bullish else "bearish", 0.75, "Strong directional candle with little shadow")

    # Hammer / Hanging Man
    if ls >= body * 2 and us <= body * 0.5 and body / rng < 0.4:
        # prior trend
        prior = data["close"].iloc[i - 5 : i].mean() if i >= 5 else c
        if c < prior:
            add("Hammer", "bullish", 0.7, "Potential bullish reversal after decline")
        else:
            add("Hanging Man", "bearish", 0.65, "Potential bearish reversal after advance")

    # Shooting Star
    if us >= body * 2 and ls <= body * 0.5 and body / rng < 0.4:
        prior = data["close"].iloc[i - 5 : i].mean() if i >= 5 else c
        if c > prior:
            add("Shooting Star", "bearish", 0.7, "Potential bearish reversal after advance")

    # Need previous candle for two-candle patterns
    if i >= 1:
        o1, h1, l1, c1 = (
            float(data["open"].iloc[i - 1]),
            float(data["high"].iloc[i - 1]),
            float(data["low"].iloc[i - 1]),
            float(data["close"].iloc[i - 1]),
        )
        body1 = _body(o1, c1)
        bull1 = c1 > o1

        # Engulfing
        if bullish and not bull1 and c >= o1 and o <= c1 and body > body1:
            add("Bullish Engulfing", "bullish", 0.8, "Current bullish candle engulfs prior bearish body")
        if not bullish and bull1 and o >= c1 and c <= o1 and body > body1:
            add("Bearish Engulfing", "bearish", 0.8, "Current bearish candle engulfs prior bullish body")

        # Harami
        if bull1 and not bullish and o < c1 and c > o1 and body < body1 * 0.6:
            add("Bearish Harami", "bearish", 0.6, "Small bearish body inside prior bullish candle")
        if not bull1 and bullish and o > c1 and c < o1 and body < body1 * 0.6:
            add("Bullish Harami", "bullish", 0.6, "Small bullish body inside prior bearish candle")

        # Piercing
        mid1 = (o1 + c1) / 2
        if not bull1 and bullish and o < l1 and c > mid1 and c < o1:
            add("Piercing", "bullish", 0.75, "Bullish reversal piercing prior bearish candle")

        # Dark Cloud Cover
        if bull1 and not bullish and o > h1 and c < mid1 and c > o1:
            add("Dark Cloud Cover", "bearish", 0.75, "Bearish reversal covering prior bullish candle")

    # Three-candle patterns
    if i >= 2:
        candles = []
        for j in range(i - 2, i + 1):
            oj, cj = float(data["open"].iloc[j]), float(data["close"].iloc[j])
            candles.append({"o": oj, "c": cj, "bull": cj > oj, "body": _body(oj, cj)})

        # Morning Star
        if (
            not candles[0]["bull"]
            and candles[1]["body"] < avg_body * 0.5
            and candles[2]["bull"]
            and candles[2]["c"] > (candles[0]["o"] + candles[0]["c"]) / 2
        ):
            add("Morning Star", "bullish", 0.85, "Three-candle bullish reversal")

        # Evening Star
        if (
            candles[0]["bull"]
            and candles[1]["body"] < avg_body * 0.5
            and not candles[2]["bull"]
            and candles[2]["c"] < (candles[0]["o"] + candles[0]["c"]) / 2
        ):
            add("Evening Star", "bearish", 0.85, "Three-candle bearish reversal")

        # Three White Soldiers
        if all(x["bull"] for x in candles) and candles[0]["c"] < candles[1]["c"] < candles[2]["c"]:
            if all(x["body"] > avg_body * 0.5 for x in candles):
                add("Three White Soldiers", "bullish", 0.85, "Strong bullish continuation")

        # Three Black Crows
        if all(not x["bull"] for x in candles) and candles[0]["c"] > candles[1]["c"] > candles[2]["c"]:
            if all(x["body"] > avg_body * 0.5 for x in candles):
                add("Three Black Crows", "bearish", 0.85, "Strong bearish continuation")

    return patterns
