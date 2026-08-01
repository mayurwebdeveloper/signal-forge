"""Unit tests for analytics engines (no network)."""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.indicators.engine import compute_all_indicators, rsi, sma
from app.patterns.candlestick import detect_candlestick_patterns
from app.patterns.chart import detect_trend, detect_chart_patterns
from app.patterns.support_resistance import calculate_support_resistance
from app.services.volume import analyze_volume
from app.backtesting.engine import run_backtest
from app.ml.predictor import predict


def _sample_df(n=120, seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0.05, 1.2, n))
    high = close + rng.uniform(0.2, 2.0, n)
    low = close - rng.uniform(0.2, 2.0, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.integers(100000, 500000, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def test_sma_rsi():
    s = pd.Series(np.arange(1, 51, dtype=float))
    assert float(sma(s, 10).iloc[-1]) == pytest.approx(45.5)
    assert 0 <= float(rsi(s, 14).iloc[-1]) <= 100


def test_indicators_suite():
    df = _sample_df()
    out = compute_all_indicators(df)
    assert "rsi_14" in out.columns
    assert "macd" in out.columns
    assert "supertrend" in out.columns


def test_candlestick_and_trend():
    df = _sample_df()
    patterns = detect_candlestick_patterns(df.reset_index())
    assert isinstance(patterns, list)
    trend = detect_trend(df)
    assert trend["trend"] in ("uptrend", "downtrend", "sideways")


def test_chart_patterns_and_sr():
    df = _sample_df(200)
    patterns = detect_chart_patterns(df)
    assert isinstance(patterns, list)
    levels = calculate_support_resistance(df)
    assert len(levels) > 0


def test_volume_and_backtest():
    df = _sample_df(150)
    vol = analyze_volume(df)
    assert "volume_score" in vol
    results, trades = run_backtest(df, "sma_crossover", capital=100000)
    assert "win_rate" in results
    assert isinstance(trades, list)


def test_prediction():
    df = _sample_df(200)
    pred = predict(df, "TEST")
    assert 0 <= pred["bullish_probability"] <= 100
    assert pred["expected_direction"] in ("Bullish", "Bearish", "Neutral")
    assert "disclaimer" in pred
