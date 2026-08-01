"""Technical indicator engine."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    cols = {c.lower(): c for c in df.columns}
    missing = required - set(cols)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    return out


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = pd.Series(np.where(avg_loss == 0, np.inf, avg_gain / avg_loss), index=series.index)
    out = 100 - (100 / (1 + rs))
    # Pure gains => 100, pure losses => 0
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    out = out.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    return out


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line, "macd_hist": hist})


def bollinger(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    mid = sma(series, period)
    std = series.rolling(period).std()
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": mid + std_dev * std,
            "bb_lower": mid - std_dev * std,
        }
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low = df["high"], df["low"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr_atr = atr(df, period)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr_atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr_atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()
    return pd.DataFrame({"adx": adx_val, "plus_di": plus_di, "minus_di": minus_di})


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    return (typical * df["volume"]).cumsum() / cum_vol


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    atr_val = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr_val
    lower = hl2 - multiplier * atr_val
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(1, index=df.index)
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = upper.iloc[i]
            continue
        if df["close"].iloc[i] > st.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < st.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
        if direction.iloc[i] == 1:
            lower.iloc[i] = max(lower.iloc[i], lower.iloc[i - 1]) if not np.isnan(lower.iloc[i - 1]) else lower.iloc[i]
            st.iloc[i] = lower.iloc[i]
        else:
            upper.iloc[i] = min(upper.iloc[i], upper.iloc[i - 1]) if not np.isnan(upper.iloc[i - 1]) else upper.iloc[i]
            st.iloc[i] = upper.iloc[i]
    return pd.DataFrame({"supertrend": st, "supertrend_dir": direction})


def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    high, low = df["high"], df["low"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    chikou = df["close"].shift(-26)
    return pd.DataFrame(
        {
            "ichimoku_tenkan": tenkan,
            "ichimoku_kijun": kijun,
            "ichimoku_span_a": senkou_a,
            "ichimoku_span_b": senkou_b,
            "ichimoku_chikou": chikou,
        }
    )


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))


def roc(series: pd.Series, period: int = 12) -> pd.Series:
    return series.pct_change(period) * 100


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highest = df["high"].rolling(period).max()
    lowest = df["low"].rolling(period).min()
    return -100 * (highest - df["close"]) / (highest - lowest).replace(0, np.nan)


def momentum(series: pd.Series, period: int = 10) -> pd.Series:
    return series.diff(period)


def pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    prev_close = df["close"].shift(1)
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high
    r2 = pivot + (prev_high - prev_low)
    s2 = pivot - (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)
    return pd.DataFrame({"pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3})


def fibonacci_retracement(df: pd.DataFrame, lookback: int = 60) -> dict[str, float]:
    window = df.tail(lookback)
    if window.empty:
        return {}
    high = float(window["high"].max())
    low = float(window["low"].min())
    diff = high - low
    levels = {
        "fib_0": high,
        "fib_236": high - 0.236 * diff,
        "fib_382": high - 0.382 * diff,
        "fib_500": high - 0.5 * diff,
        "fib_618": high - 0.618 * diff,
        "fib_786": high - 0.786 * diff,
        "fib_100": low,
    }
    return {k: round(v, 4) for k, v in levels.items()}


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute full indicator suite and return enriched DataFrame."""
    data = _ensure_ohlcv(df)
    close = data["close"]

    result = data.copy()
    result["sma_20"] = sma(close, 20)
    result["sma_50"] = sma(close, 50)
    result["sma_200"] = sma(close, 200)
    result["ema_9"] = ema(close, 9)
    result["ema_21"] = ema(close, 21)
    result["ema_50"] = ema(close, 50)
    result["rsi_14"] = rsi(close, 14)
    result = result.join(macd(close))
    result = result.join(bollinger(close))
    result["atr_14"] = atr(result)
    result = result.join(adx(result))
    result["vwap"] = vwap(result)
    result = result.join(supertrend(result))
    result = result.join(ichimoku(result))
    result["obv"] = obv(result)
    result["cci_20"] = cci(result)
    result["roc_12"] = roc(close)
    result["williams_r"] = williams_r(result)
    result["momentum_10"] = momentum(close)
    result = result.join(pivot_points(result))

    # Golden / Death cross flags
    result["golden_cross"] = (result["sma_50"] > result["sma_200"]) & (
        result["sma_50"].shift(1) <= result["sma_200"].shift(1)
    )
    result["death_cross"] = (result["sma_50"] < result["sma_200"]) & (
        result["sma_50"].shift(1) >= result["sma_200"].shift(1)
    )
    result["ema_bull_cross"] = (result["ema_9"] > result["ema_21"]) & (
        result["ema_9"].shift(1) <= result["ema_21"].shift(1)
    )
    result["ema_bear_cross"] = (result["ema_9"] < result["ema_21"]) & (
        result["ema_9"].shift(1) >= result["ema_21"].shift(1)
    )

    return result


def latest_indicator_dict(df: pd.DataFrame) -> dict:
    enriched = compute_all_indicators(df)
    last = enriched.iloc[-1]
    fib = fibonacci_retracement(enriched)
    out = {}
    for col in enriched.columns:
        val = last[col]
        if pd.isna(val):
            continue
        if isinstance(val, (np.bool_, bool)):
            out[col] = bool(val)
        elif isinstance(val, (np.integer, int)):
            out[col] = int(val)
        elif isinstance(val, (np.floating, float)):
            out[col] = round(float(val), 6)
        else:
            out[col] = val
    out.update(fib)
    return out
