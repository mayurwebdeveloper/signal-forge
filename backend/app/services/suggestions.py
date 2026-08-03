"""Daily next-session stock suggestions (system-wide ranked picks)."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.database.models import AIPrediction, DailySuggestion, Stock, SystemSetting
from app.indicators.engine import compute_all_indicators
from app.patterns.chart import detect_trend
from app.services.data_downloader import get_price_dataframe
from app.services.volume import analyze_volume

DEFAULT_SETTINGS = {
    "suggestions_enabled": ("true", "Show daily next-session stock suggestions to users"),
    "suggestions_min_count": ("10", "Minimum number of suggested stocks each day"),
    "suggestions_max_count": ("20", "Maximum number of suggested stocks each day"),
    "suggestions_min_bullish_pct": ("50", "Prefer stocks with at least this next-day bullish score"),
}

DISCLAIMER = (
    "Statistical next-session setup ranking based on historical patterns and indicators. "
    "Not financial advice. No guarantee of future prices or profits."
)


def ensure_default_settings(db: Session) -> None:
    for key, (value, description) in DEFAULT_SETTINGS.items():
        existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not existing:
            db.add(SystemSetting(key=key, value=value, description=description))
    db.commit()


def get_settings_map(db: Session) -> dict[str, str]:
    ensure_default_settings(db)
    rows = db.query(SystemSetting).all()
    return {r.key: r.value for r in rows}


def get_suggestion_settings(db: Session) -> dict:
    raw = get_settings_map(db)
    return {
        "suggestions_enabled": raw.get("suggestions_enabled", "true").lower() in ("1", "true", "yes"),
        "suggestions_min_count": max(5, int(float(raw.get("suggestions_min_count", "10")))),
        "suggestions_max_count": max(10, int(float(raw.get("suggestions_max_count", "20")))),
        "suggestions_min_bullish_pct": float(raw.get("suggestions_min_bullish_pct", "50")),
    }


def update_suggestion_settings(db: Session, payload: dict) -> dict:
    ensure_default_settings(db)
    mapping = {
        "suggestions_enabled": lambda v: "true" if v else "false",
        "suggestions_min_count": lambda v: str(int(v)),
        "suggestions_max_count": lambda v: str(int(v)),
        "suggestions_min_bullish_pct": lambda v: str(float(v)),
    }
    for key, converter in mapping.items():
        if key not in payload or payload[key] is None:
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not row:
            row = SystemSetting(key=key, value=converter(payload[key]), description=DEFAULT_SETTINGS.get(key, ("", ""))[1])
            db.add(row)
        else:
            row.value = converter(payload[key])
            row.updated_at = datetime.utcnow()
    db.commit()
    return get_suggestion_settings(db)


def _latest_prediction(db: Session, stock_id: int) -> AIPrediction | None:
    return (
        db.query(AIPrediction)
        .filter(AIPrediction.stock_id == stock_id)
        .order_by(AIPrediction.created_at.desc())
        .first()
    )


def _score_next_day(df: pd.DataFrame, prediction: dict | None) -> dict:
    """Composite next-session setup score with human-readable reasons."""
    enriched = compute_all_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2] if len(enriched) > 1 else last
    close = float(last["close"])
    change_pct = float((close / float(prev["close"]) - 1) * 100) if float(prev["close"]) else 0.0

    trend = detect_trend(df)
    vol = analyze_volume(df)
    reasons: list[str] = []
    score = 45.0

    rsi_v = float(last.get("rsi_14", 50) or 50)
    if 40 <= rsi_v <= 62:
        score += 10
        reasons.append(f"RSI in constructive zone ({rsi_v:.0f})")
    elif rsi_v < 32:
        score += 6
        reasons.append(f"Oversold bounce setup (RSI {rsi_v:.0f})")
    elif rsi_v > 72:
        score -= 10
        reasons.append(f"Extended RSI ({rsi_v:.0f}) — caution")

    macd_h = float(last.get("macd_hist", 0) or 0)
    macd_prev = float(prev.get("macd_hist", 0) or 0)
    if macd_h > 0 and macd_h >= macd_prev:
        score += 9
        reasons.append("MACD histogram expanding bullish")
    elif macd_h > 0:
        score += 4
        reasons.append("MACD still positive")
    elif macd_h < 0 and macd_h > macd_prev:
        score += 5
        reasons.append("MACD bearish momentum fading")
    else:
        score -= 6

    if trend["trend"] == "uptrend":
        score += 8 * float(trend.get("strength") or 0.5)
        reasons.append("Short-term uptrend")
    elif trend["trend"] == "downtrend":
        score -= 8 * float(trend.get("strength") or 0.5)
        reasons.append("Short-term downtrend")

    buy_pressure = float(vol.get("buying_pressure") or 0.5)
    if buy_pressure >= 0.58:
        score += 8
        reasons.append("Elevated buying pressure")
    elif buy_pressure <= 0.42:
        score -= 6
        reasons.append("Selling pressure elevated")

    if last.get("golden_cross"):
        score += 10
        reasons.append("Golden cross active")
    if last.get("ema_bull_cross"):
        score += 6
        reasons.append("EMA bullish cross")
    if last.get("death_cross"):
        score -= 10
        reasons.append("Death cross — avoid as top pick")

    look = enriched.tail(20)
    resist = float(look["high"].iloc[:-1].max()) if len(look) > 1 else close
    if close > resist * 1.005:
        score += 8
        reasons.append("Near-term breakout above recent highs")
    elif close > resist * 0.985:
        score += 4
        reasons.append("Pressing against recent resistance")

    # Blend stored / live AI probability (5-day model) as a soft prior for next day
    if prediction:
        bull = float(prediction.get("bullish_probability") or 50)
        score += (bull - 50) * 0.35
        if bull >= 58:
            reasons.append(f"AI bias bullish ({bull:.0f}%)")
        conf = prediction.get("confidence") or "Medium"
        if conf == "High":
            score += 4
        elif conf == "Low":
            score -= 2
        risk = prediction.get("risk") or "Medium"
        if risk == "High":
            score -= 5
            reasons.append("Higher volatility risk")
        elif risk == "Low":
            score += 3
            reasons.append("Lower volatility risk")

    # Mild mean-reversion / continuation from today's move
    if 0.4 <= change_pct <= 2.5:
        score += 4
        reasons.append("Healthy positive day without extreme chase")
    elif change_pct > 4:
        score -= 4
        reasons.append("Large one-day spike — next-day follow-through less reliable")
    elif change_pct < -2.5 and rsi_v < 40:
        score += 3
        reasons.append("Pullback into softer RSI — watch for bounce")

    next_day_prob = float(np.clip(score, 8, 92))
    direction = "Bullish" if next_day_prob >= 55 else ("Bearish" if next_day_prob <= 45 else "Neutral")
    confidence = "High" if abs(next_day_prob - 50) > 18 else ("Medium" if abs(next_day_prob - 50) > 8 else "Low")
    atr = float(last.get("atr_14", 0) or 0)
    risk = "High" if atr / close > 0.03 else ("Low" if atr / close < 0.015 else "Medium")

    if not reasons:
        reasons.append("Balanced technical profile")

    return {
        "score": round(next_day_prob, 2),
        "next_day_probability": round(next_day_prob, 2),
        "expected_direction": direction,
        "confidence": confidence,
        "risk": risk,
        "price": round(close, 4),
        "change_pct": round(change_pct, 3),
        "reasons": reasons[:6],
        "features": {
            "rsi": round(rsi_v, 2),
            "macd_hist": round(macd_h, 4),
            "trend": trend.get("trend"),
            "buying_pressure": round(buy_pressure, 3),
            "volume_score": vol.get("volume_score"),
            "ai_bullish": prediction.get("bullish_probability") if prediction else None,
        },
    }


def generate_daily_suggestions(db: Session, for_date: date | None = None, force: bool = False) -> dict:
    """Rank and persist at least N next-session stock suggestions for the day."""
    settings = get_suggestion_settings(db)
    if not settings["suggestions_enabled"] and not force:
        return {"generated": False, "reason": "suggestions_disabled", "count": 0, "date": str(for_date or date.today())}

    target_date = for_date or date.today()
    min_count = settings["suggestions_min_count"]
    max_count = max(settings["suggestions_max_count"], min_count)
    min_bull = settings["suggestions_min_bullish_pct"]

    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    candidates: list[dict] = []

    for stock in stocks:
        # Prefer tradable equities — skip bare indices from the daily stock list
        if stock.symbol.startswith("^"):
            continue
        df = get_price_dataframe(db, stock.id, timeframe="1d", limit=160)
        if df.empty or len(df) < 40:
            continue

        pred_row = _latest_prediction(db, stock.id)
        pred_dict = None
        if pred_row:
            pred_dict = {
                "bullish_probability": pred_row.bullish_probability,
                "bearish_probability": pred_row.bearish_probability,
                "expected_direction": pred_row.expected_direction,
                "confidence": pred_row.confidence,
                "risk": pred_row.risk,
                "scores": pred_row.scores,
            }

        scored = _score_next_day(df, pred_dict)
        candidates.append(
            {
                "stock_id": stock.id,
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "exchange": stock.exchange,
                **scored,
            }
        )

    # Prefer constructive setups first, then fill to min_count
    preferred = [c for c in candidates if c["next_day_probability"] >= min_bull]
    preferred.sort(key=lambda x: x["score"], reverse=True)
    rest = [c for c in candidates if c["next_day_probability"] < min_bull]
    rest.sort(key=lambda x: x["score"], reverse=True)

    selected = preferred[:max_count]
    if len(selected) < min_count:
        need = min_count - len(selected)
        selected.extend(rest[:need])

    # If still short (tiny universe), take whatever we have sorted by score
    if len(selected) < min_count:
        all_sorted = sorted(candidates, key=lambda x: x["score"], reverse=True)
        selected = all_sorted[: max(min_count, min(len(all_sorted), max_count))]

    selected = selected[:max_count]

    db.query(DailySuggestion).filter(DailySuggestion.suggestion_date == target_date).delete()
    for idx, item in enumerate(selected, start=1):
        db.add(
            DailySuggestion(
                suggestion_date=target_date,
                stock_id=item["stock_id"],
                rank=idx,
                score=item["score"],
                next_day_probability=item["next_day_probability"],
                expected_direction=item["expected_direction"],
                confidence=item["confidence"],
                risk=item["risk"],
                price=item["price"],
                change_pct=item["change_pct"],
                reasons=item["reasons"],
                features=item["features"],
            )
        )
    db.commit()

    return {
        "generated": True,
        "date": str(target_date),
        "count": len(selected),
        "min_count": min_count,
        "disclaimer": DISCLAIMER,
    }


def list_daily_suggestions(db: Session, for_date: date | None = None, auto_generate: bool = True) -> dict:
    settings = get_suggestion_settings(db)
    target_date = for_date or date.today()

    if not settings["suggestions_enabled"]:
        return {
            "enabled": False,
            "date": str(target_date),
            "count": 0,
            "suggestions": [],
            "disclaimer": DISCLAIMER,
            "settings": settings,
        }

    rows = (
        db.query(DailySuggestion)
        .filter(DailySuggestion.suggestion_date == target_date)
        .order_by(DailySuggestion.rank.asc())
        .all()
    )

    if (not rows or len(rows) < settings["suggestions_min_count"]) and auto_generate:
        generate_daily_suggestions(db, for_date=target_date)
        rows = (
            db.query(DailySuggestion)
            .filter(DailySuggestion.suggestion_date == target_date)
            .order_by(DailySuggestion.rank.asc())
            .all()
        )

    suggestions = []
    for row in rows:
        stock = db.get(Stock, row.stock_id)
        if not stock:
            continue
        suggestions.append(
            {
                "id": row.id,
                "rank": row.rank,
                "stock_id": row.stock_id,
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "exchange": stock.exchange,
                "score": row.score,
                "next_day_probability": row.next_day_probability,
                "expected_direction": row.expected_direction,
                "confidence": row.confidence,
                "risk": row.risk,
                "price": row.price,
                "change_pct": row.change_pct,
                "reasons": row.reasons or [],
                "features": row.features or {},
            }
        )

    return {
        "enabled": True,
        "date": str(target_date),
        "count": len(suggestions),
        "suggestions": suggestions,
        "disclaimer": DISCLAIMER,
        "settings": settings,
    }
