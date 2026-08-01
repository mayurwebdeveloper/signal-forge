"""AI probability scoring engine (ensemble: RF + XGB + Logistic)."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.core.config import MODELS_DIR
from app.indicators.engine import compute_all_indicators
from app.patterns.chart import detect_trend
from app.patterns.support_resistance import calculate_support_resistance, nearest_levels
from app.services.volume import analyze_volume

FEATURE_COLS = [
    "rsi_14",
    "macd",
    "macd_hist",
    "adx",
    "atr_14",
    "cci_20",
    "roc_12",
    "williams_r",
    "momentum_10",
    "sma_20",
    "sma_50",
    "ema_9",
    "ema_21",
    "bb_upper",
    "bb_lower",
    "close",
    "volume",
]


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    enriched = compute_all_indicators(df)
    feat = enriched.copy()
    feat["ret_1"] = feat["close"].pct_change(1)
    feat["ret_5"] = feat["close"].pct_change(5)
    feat["ret_10"] = feat["close"].pct_change(10)
    feat["vol_chg"] = feat["volume"].pct_change(5)
    feat["price_vs_sma20"] = feat["close"] / feat["sma_20"] - 1
    feat["price_vs_sma50"] = feat["close"] / feat["sma_50"] - 1
    feat["bb_pos"] = (feat["close"] - feat["bb_lower"]) / (feat["bb_upper"] - feat["bb_lower"]).replace(0, np.nan)
    # Forward label: price up in next 5 days
    feat["label"] = (feat["close"].shift(-5) > feat["close"]).astype(int)
    return feat


def _feature_matrix(feat: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    cols = FEATURE_COLS + ["ret_1", "ret_5", "ret_10", "vol_chg", "price_vs_sma20", "price_vs_sma50", "bb_pos"]
    available = [c for c in cols if c in feat.columns]
    X = feat[available].replace([np.inf, -np.inf], np.nan).dropna()
    return X, available


def train_models(df: pd.DataFrame, symbol: str = "generic") -> dict:
    feat = _build_features(df)
    X, cols = _feature_matrix(feat)
    y = feat.loc[X.index, "label"].dropna()
    common = X.index.intersection(y.index)
    X, y = X.loc[common], y.loc[common]
    # Drop last rows without labels
    valid = y.notna()
    X, y = X[valid], y[valid]
    if len(X) < 80:
        return {"trained": False, "reason": "insufficient_data", "samples": len(X)}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    rf = RandomForestClassifier(n_estimators=120, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    lr = LogisticRegression(max_iter=500, random_state=42)
    lr.fit(X_train_s, y_train)

    models = {"rf": rf, "lr": lr, "scaler": scaler, "features": cols}

    try:
        from xgboost import XGBClassifier

        xgb = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        )
        xgb.fit(X_train, y_train)
        models["xgb"] = xgb
    except Exception:
        pass

    # Accuracy snapshot
    acc_rf = float(rf.score(X_test, y_test))
    acc_lr = float(lr.score(X_test_s, y_test))
    path = MODELS_DIR / f"model_{symbol.replace('.', '_')}.joblib"
    joblib.dump(models, path)
    return {
        "trained": True,
        "path": str(path),
        "samples": len(X),
        "accuracy_rf": round(acc_rf, 4),
        "accuracy_lr": round(acc_lr, 4),
        "features": cols,
    }


def _load_or_train(df: pd.DataFrame, symbol: str) -> dict | None:
    path = MODELS_DIR / f"model_{symbol.replace('.', '_')}.joblib"
    if path.exists():
        try:
            return joblib.load(path)
        except Exception:
            pass
    result = train_models(df, symbol)
    if result.get("trained"):
        return joblib.load(result["path"])
    return None


def _heuristic_probability(df: pd.DataFrame) -> dict:
    """Fallback scoring when ML models cannot train."""
    enriched = compute_all_indicators(df)
    last = enriched.iloc[-1]
    trend = detect_trend(df)
    vol = analyze_volume(df)
    levels = calculate_support_resistance(df)
    near = nearest_levels(levels, float(last["close"]))

    score = 50.0
    rsi_v = float(last.get("rsi_14", 50) or 50)
    if rsi_v < 30:
        score += 12
    elif rsi_v > 70:
        score -= 12
    elif rsi_v > 50:
        score += 5
    else:
        score -= 3

    macd_h = float(last.get("macd_hist", 0) or 0)
    score += np.clip(macd_h / (abs(float(last["close"])) * 0.001 + 1e-6) * 2, -10, 10)

    if trend["trend"] == "uptrend":
        score += 10 * trend["strength"]
    elif trend["trend"] == "downtrend":
        score -= 10 * trend["strength"]

    score += (vol["buying_pressure"] - 0.5) * 20
    if last.get("golden_cross"):
        score += 8
    if last.get("death_cross"):
        score -= 8
    if last.get("ema_bull_cross"):
        score += 5
    if last.get("ema_bear_cross"):
        score -= 5

    bullish = float(np.clip(score, 5, 95))
    bearish = 100 - bullish
    confidence = "High" if abs(bullish - 50) > 20 else ("Medium" if abs(bullish - 50) > 10 else "Low")
    direction = "Bullish" if bullish >= 55 else ("Bearish" if bullish <= 45 else "Neutral")
    risk = "High" if float(last.get("atr_14", 0) or 0) / float(last["close"]) > 0.03 else (
        "Low" if float(last.get("atr_14", 0) or 0) / float(last["close"]) < 0.015 else "Medium"
    )

    return {
        "bullish_probability": round(bullish, 2),
        "bearish_probability": round(bearish, 2),
        "expected_direction": direction,
        "confidence": confidence,
        "holding_period": "3-10 Trading Days",
        "risk": risk,
        "scores": {
            "bullish_score": round(bullish, 2),
            "bearish_score": round(bearish, 2),
            "trend_score": trend["score"],
            "momentum_score": round(np.clip(50 + (rsi_v - 50), 0, 100), 2),
            "volume_score": vol["volume_score"],
            "risk_score": {"Low": 25, "Medium": 50, "High": 75}[risk],
            "confidence_score": {"Low": 40, "Medium": 65, "High": 85}[confidence],
            "pattern_strength": 0.5,
            "support_distance": near.get("support_distance_pct"),
            "resistance_distance": near.get("resistance_distance_pct"),
        },
        "features_used": {"method": "heuristic"},
        "model_version": "v1-heuristic",
    }


def predict(df: pd.DataFrame, symbol: str = "generic") -> dict:
    disclaimer = "Estimate based on historical data, not a certainty. Not financial advice."
    if len(df) < 60:
        result = _heuristic_probability(df)
        result["disclaimer"] = disclaimer
        return result

    models = _load_or_train(df, symbol)
    if not models:
        result = _heuristic_probability(df)
        result["disclaimer"] = disclaimer
        return result

    feat = _build_features(df)
    cols = models["features"]
    row = feat[cols].replace([np.inf, -np.inf], np.nan).dropna()
    if row.empty:
        result = _heuristic_probability(df)
        result["disclaimer"] = disclaimer
        return result

    x = row.iloc[[-1]]
    probs = []
    probs.append(float(models["rf"].predict_proba(x)[0][1]))
    xs = models["scaler"].transform(x)
    probs.append(float(models["lr"].predict_proba(xs)[0][1]))
    if "xgb" in models:
        try:
            probs.append(float(models["xgb"].predict_proba(x)[0][1]))
        except Exception:
            pass

    bullish = float(np.mean(probs) * 100)
    bearish = 100 - bullish
    confidence = "High" if abs(bullish - 50) > 20 else ("Medium" if abs(bullish - 50) > 10 else "Low")
    direction = "Bullish" if bullish >= 55 else ("Bearish" if bullish <= 45 else "Neutral")

    # Enrich with KPI scores
    heur = _heuristic_probability(df)
    scores = heur["scores"]
    scores["bullish_score"] = round(bullish, 2)
    scores["bearish_score"] = round(bearish, 2)

    atr = float(feat.iloc[-1].get("atr_14", 0) or 0)
    close = float(feat.iloc[-1]["close"])
    risk = "High" if atr / close > 0.03 else ("Low" if atr / close < 0.015 else "Medium")

    return {
        "bullish_probability": round(bullish, 2),
        "bearish_probability": round(bearish, 2),
        "expected_direction": direction,
        "confidence": confidence,
        "holding_period": "3-10 Trading Days",
        "risk": risk,
        "scores": scores,
        "features_used": {"method": "ensemble", "models": list(models.keys()), "n_features": len(cols)},
        "model_version": "v1-ensemble",
        "disclaimer": disclaimer,
    }
