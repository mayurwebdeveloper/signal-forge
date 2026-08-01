"""Orchestrates analysis pipeline for a stock."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.database.models import (
    AIPrediction,
    CandlestickPattern,
    ChartPattern,
    Stock,
    SupportResistance,
    TechnicalIndicator,
)
from app.indicators.engine import compute_all_indicators, latest_indicator_dict
from app.ml.predictor import predict
from app.patterns.candlestick import detect_candlestick_patterns
from app.patterns.chart import detect_chart_patterns, detect_trend
from app.patterns.support_resistance import calculate_support_resistance, nearest_levels
from app.services.data_downloader import download_stock_data, get_price_dataframe
from app.services.volume import analyze_volume


def ensure_stock_prices(db: Session, stock: Stock, period: str = "2y", min_bars: int = 30) -> dict:
    """Download history automatically when missing or too short."""
    df = get_price_dataframe(db, stock.id, timeframe="1d")
    if not df.empty and len(df) >= min_bars:
        return {"downloaded": False, "rows": len(df)}
    result = download_stock_data(db, stock, period=period)
    df2 = get_price_dataframe(db, stock.id, timeframe="1d")
    return {
        "downloaded": True,
        "rows": len(df2),
        "detail": result,
        "error": result.get("error") if result.get("rows", 0) == 0 else None,
    }


def analyze_stock(db: Session, stock: Stock, persist: bool = True, auto_download: bool = True) -> dict:
    df = get_price_dataframe(db, stock.id, timeframe="1d")
    if (df.empty or len(df) < 30) and auto_download:
        ensure_stock_prices(db, stock, period="2y", min_bars=30)
        df = get_price_dataframe(db, stock.id, timeframe="1d")

    if df.empty or len(df) < 30:
        return {
            "error": (
                f"No usable price data for {stock.symbol} from Yahoo Finance. "
                "The symbol may be delisted or renamed."
            ),
            "stock_id": stock.id,
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "needs_download": False,
        }

    indicators = latest_indicator_dict(df)
    candle_patterns = detect_candlestick_patterns(df.reset_index())
    chart_patterns = detect_chart_patterns(df)
    trend = detect_trend(df)
    levels = calculate_support_resistance(df)
    near = nearest_levels(levels, float(df["close"].iloc[-1]))
    volume = analyze_volume(df)
    prediction = predict(df, stock.symbol)

    # Pattern strength from detected patterns
    strengths = [p.get("strength", 0.5) for p in chart_patterns + candle_patterns]
    pattern_strength = round(sum(strengths) / len(strengths), 3) if strengths else 0.3
    if prediction.get("scores"):
        prediction["scores"]["pattern_strength"] = pattern_strength

    result = {
        "stock_id": stock.id,
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "latest_price": round(float(df["close"].iloc[-1]), 4),
        "change_pct": round(float(df["close"].pct_change().iloc[-1] * 100), 3) if len(df) > 1 else 0,
        "indicators": indicators,
        "candlestick_patterns": candle_patterns,
        "chart_patterns": chart_patterns,
        "trend": trend,
        "support_resistance": levels,
        "nearest_levels": near,
        "volume": volume,
        "prediction": prediction,
    }

    if persist:
        _persist_analysis(db, stock, df, indicators, candle_patterns, chart_patterns, levels, prediction)

    return result


def _persist_analysis(db, stock, df, indicators, candle_patterns, chart_patterns, levels, prediction):
    last_date = df.index[-1].date() if hasattr(df.index[-1], "date") else df.index[-1]

    # Indicators — upsert latest
    existing = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock.id, TechnicalIndicator.date == last_date)
        .first()
    )
    # Store only serializable subset
    clean_ind = {k: v for k, v in indicators.items() if isinstance(v, (int, float, bool, str))}
    if existing:
        existing.data = clean_ind
    else:
        db.add(TechnicalIndicator(stock_id=stock.id, date=last_date, data=clean_ind))

    # Clear recent pattern rows for stock (keep DB lean)
    db.query(CandlestickPattern).filter(CandlestickPattern.stock_id == stock.id).delete()
    for p in candle_patterns:
        d = p.get("date")
        if hasattr(d, "date"):
            d = d.date()
        elif d is None:
            d = last_date
        db.add(
            CandlestickPattern(
                stock_id=stock.id,
                date=d,
                pattern_name=p["pattern_name"],
                signal=p["signal"],
                strength=p["strength"],
                description=p.get("description"),
            )
        )

    db.query(ChartPattern).filter(ChartPattern.stock_id == stock.id).delete()
    for p in chart_patterns:
        db.add(
            ChartPattern(
                stock_id=stock.id,
                pattern_name=p["pattern_name"],
                signal=p["signal"],
                start_date=p.get("start_date"),
                end_date=p.get("end_date"),
                strength=p["strength"],
                target_price=p.get("target_price"),
                stop_loss=p.get("stop_loss"),
                meta=p.get("meta"),
            )
        )

    db.query(SupportResistance).filter(SupportResistance.stock_id == stock.id).delete()
    for lvl in levels:
        db.add(
            SupportResistance(
                stock_id=stock.id,
                level_type=lvl["level_type"],
                price=lvl["price"],
                strength=lvl["strength"],
                touches=lvl.get("touches", 1),
                date=lvl.get("date"),
                meta=lvl.get("meta"),
            )
        )

    db.add(
        AIPrediction(
            stock_id=stock.id,
            bullish_probability=prediction["bullish_probability"],
            bearish_probability=prediction["bearish_probability"],
            expected_direction=prediction["expected_direction"],
            confidence=prediction["confidence"],
            holding_period=prediction.get("holding_period", "3-10 Trading Days"),
            risk=prediction.get("risk", "Medium"),
            scores=prediction.get("scores"),
            features_used=prediction.get("features_used"),
            model_version=prediction.get("model_version", "v1"),
            disclaimer=prediction.get("disclaimer", ""),
        )
    )
    db.commit()


def scan_stocks(db: Session, filters) -> list[dict]:
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    results = []
    for stock in stocks:
        df = get_price_dataframe(db, stock.id, timeframe="1d")
        if df.empty or len(df) < 50:
            continue
        enriched = compute_all_indicators(df)
        last = enriched.iloc[-1]
        price = float(last["close"])
        volume = float(last["volume"])
        rsi_v = float(last["rsi_14"]) if not pd_isna(last.get("rsi_14")) else None
        change = float(enriched["close"].pct_change().iloc[-1] * 100)

        # 52w
        year = enriched.tail(252) if len(enriched) >= 252 else enriched
        high_52 = float(year["high"].max())
        low_52 = float(year["low"].min())

        item = {
            "stock_id": stock.id,
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "market_cap": stock.market_cap,
            "price": round(price, 4),
            "change_pct": round(change, 3),
            "volume": volume,
            "rsi": round(rsi_v, 2) if rsi_v is not None else None,
            "macd": round(float(last["macd"]), 4) if not pd_isna(last.get("macd")) else None,
            "macd_hist": round(float(last["macd_hist"]), 4) if not pd_isna(last.get("macd_hist")) else None,
            "golden_cross": bool(last.get("golden_cross")) if not pd_isna(last.get("golden_cross")) else False,
            "death_cross": bool(last.get("death_cross")) if not pd_isna(last.get("death_cross")) else False,
            "ema_bull_cross": bool(last.get("ema_bull_cross")) if not pd_isna(last.get("ema_bull_cross")) else False,
            "high_52w": round(high_52, 4),
            "low_52w": round(low_52, 4),
            "near_52w_high": price >= high_52 * 0.97,
            "near_52w_low": price <= low_52 * 1.03,
        }

        levels = calculate_support_resistance(df)
        near = nearest_levels(levels, price)
        item["near_support"] = (near.get("support_distance_pct") or 99) < 2
        item["near_resistance"] = (near.get("resistance_distance_pct") or 99) < 2

        look = enriched.tail(20)
        resist = float(look["high"].iloc[:-1].max())
        item["breakout"] = price > resist * 1.005

        if _passes_filters(item, filters, last):
            results.append(item)

    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results[: filters.limit]


def pd_isna(v) -> bool:
    try:
        import pandas as pd

        return bool(pd.isna(v))
    except Exception:
        return v is None


def _passes_filters(item: dict, f, last) -> bool:
    if f.min_price is not None and item["price"] < f.min_price:
        return False
    if f.max_price is not None and item["price"] > f.max_price:
        return False
    if f.min_volume is not None and item["volume"] < f.min_volume:
        return False
    if f.sector and (item.get("sector") or "").lower() != f.sector.lower():
        return False
    if f.min_market_cap is not None and (item.get("market_cap") or 0) < f.min_market_cap:
        return False
    if f.max_market_cap is not None and (item.get("market_cap") or float("inf")) > f.max_market_cap:
        return False
    if f.min_rsi is not None and (item.get("rsi") is None or item["rsi"] < f.min_rsi):
        return False
    if f.max_rsi is not None and (item.get("rsi") is None or item["rsi"] > f.max_rsi):
        return False
    if f.macd_signal == "bullish" and not (item.get("macd_hist") and item["macd_hist"] > 0):
        return False
    if f.macd_signal == "bearish" and not (item.get("macd_hist") and item["macd_hist"] < 0):
        return False
    if f.ema_cross == "bullish" and not item.get("ema_bull_cross"):
        return False
    if f.golden_cross and not item.get("golden_cross"):
        return False
    if f.death_cross and not item.get("death_cross"):
        return False
    if f.breakout and not item.get("breakout"):
        return False
    if f.near_support and not item.get("near_support"):
        return False
    if f.near_resistance and not item.get("near_resistance"):
        return False
    if f.near_52w_high and not item.get("near_52w_high"):
        return False
    if f.near_52w_low and not item.get("near_52w_low"):
        return False
    return True
