"""Stock and market data routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_current_user
from app.database import get_db
from app.database.models import AIPrediction, CandlestickPattern, ChartPattern, Stock, SupportResistance, User
from app.database.schemas import MessageOut, PriceBar, StockCreate, StockDetailOut, StockOut
from app.services.analysis import analyze_stock
from app.services.data_downloader import (
    download_stock_data,
    fetch_ticker_info,
    get_price_dataframe,
    normalize_symbol,
    search_yahoo_symbols,
    seed_stocks,
)
from app.services.volume import analyze_volume

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("", response_model=list[StockOut])
def list_stocks(
    q: str | None = None,
    sector: str | None = None,
    exchange: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Stock).filter(Stock.is_active == True)  # noqa: E712
    if q:
        like = f"%{q}%"
        query = query.filter((Stock.symbol.ilike(like)) | (Stock.company_name.ilike(like)))
    if sector:
        query = query.filter(Stock.sector.ilike(sector))
    if exchange:
        query = query.filter(Stock.exchange.ilike(exchange))
    return query.order_by(Stock.symbol).all()


@router.post("/seed", response_model=MessageOut)
def seed(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    added = seed_stocks(db)
    return MessageOut(message=f"Seeded {added} stocks")


@router.get("/lookup")
def lookup_symbols(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(12, ge=1, le=25),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search Yahoo Finance + local DB for symbols to add."""
    remote = search_yahoo_symbols(q, limit=limit)
    like = f"%{q}%"
    local = (
        db.query(Stock)
        .filter((Stock.symbol.ilike(like)) | (Stock.company_name.ilike(like)), Stock.is_active == True)  # noqa: E712
        .limit(limit)
        .all()
    )
    tracked = {s.symbol: s.id for s in db.query(Stock).filter(Stock.symbol.in_([r["symbol"] for r in remote] or ["__none__"])).all()}
    for s in local:
        tracked[s.symbol] = s.id

    out = []
    seen = set()
    for s in local:
        seen.add(s.symbol)
        out.append(
            {
                "symbol": s.symbol,
                "company_name": s.company_name,
                "exchange": s.exchange,
                "quote_type": "LOCAL",
                "already_tracked": True,
                "stock_id": s.id,
            }
        )
    for r in remote:
        if r["symbol"] in seen:
            continue
        seen.add(r["symbol"])
        sid = tracked.get(r["symbol"])
        out.append({**r, "already_tracked": sid is not None, "stock_id": sid})
    return {"query": q, "results": out[:limit]}


@router.post("", response_model=StockOut, status_code=201)
def add_stock(payload: StockCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    symbol = normalize_symbol(payload.symbol)
    existing = db.query(Stock).filter(Stock.symbol == symbol).first()
    if existing:
        return existing
    info = fetch_ticker_info(symbol)
    stock = Stock(
        symbol=symbol,
        company_name=payload.company_name or info.get("company_name", symbol),
        exchange=payload.exchange or info.get("exchange", "NSE"),
        sector=payload.sector or info.get("sector"),
        industry=payload.industry or info.get("industry"),
        isin=payload.isin,
        market_cap=payload.market_cap or info.get("market_cap"),
        currency=info.get("currency", "INR"),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    download_stock_data(db, stock, period="2y")
    try:
        analyze_stock(db, stock, persist=True, auto_download=False)
    except Exception:
        pass
    return stock


@router.get("/{stock_id}", response_model=StockDetailOut)
def get_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    df = get_price_dataframe(db, stock.id)
    latest = change = volume = None
    if not df.empty:
        latest = round(float(df["close"].iloc[-1]), 4)
        change = round(float(df["close"].pct_change().iloc[-1] * 100), 3) if len(df) > 1 else 0
        volume = float(df["volume"].iloc[-1])
    return StockDetailOut(
        id=stock.id,
        symbol=stock.symbol,
        company_name=stock.company_name,
        exchange=stock.exchange,
        sector=stock.sector,
        industry=stock.industry,
        isin=stock.isin,
        market_cap=stock.market_cap,
        currency=stock.currency,
        is_active=stock.is_active,
        last_updated=stock.last_updated,
        latest_price=latest,
        change_pct=change,
        volume=volume,
    )


@router.get("/{stock_id}/prices", response_model=list[PriceBar])
def get_prices(
    stock_id: int,
    timeframe: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
):
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    df = get_price_dataframe(db, stock_id, timeframe=timeframe, limit=limit)
    if df.empty and timeframe == "1d":
        from app.services.analysis import ensure_stock_prices

        ensure_stock_prices(db, stock, period="2y")
        df = get_price_dataframe(db, stock_id, timeframe=timeframe, limit=limit)
    if df.empty:
        return []
    out = []
    for idx, row in df.iterrows():
        out.append(
            PriceBar(
                date=idx.date() if hasattr(idx, "date") else idx,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adj_close=float(row["adj_close"]),
                volume=float(row["volume"]),
            )
        )
    return out


@router.post("/{stock_id}/download", response_model=MessageOut)
def download(stock_id: int, period: str = "5y", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    result = download_stock_data(db, stock, period=period)
    return MessageOut(message="Download complete", detail=result)


@router.get("/{stock_id}/analysis")
def get_analysis(stock_id: int, persist: bool = True, db: Session = Depends(get_db)):
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return analyze_stock(db, stock, persist=persist)


@router.get("/{stock_id}/indicators")
def get_indicators(stock_id: int, db: Session = Depends(get_db)):
    result = get_analysis_safe(db, stock_id)
    return result.get("indicators", {})


@router.get("/{stock_id}/patterns")
def get_patterns(stock_id: int, db: Session = Depends(get_db)):
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {
        "candlestick": [
            {
                "date": str(p.date),
                "pattern_name": p.pattern_name,
                "signal": p.signal,
                "strength": p.strength,
                "description": p.description,
            }
            for p in db.query(CandlestickPattern).filter(CandlestickPattern.stock_id == stock_id).all()
        ],
        "chart": [
            {
                "pattern_name": p.pattern_name,
                "signal": p.signal,
                "strength": p.strength,
                "start_date": str(p.start_date) if p.start_date else None,
                "end_date": str(p.end_date) if p.end_date else None,
                "target_price": p.target_price,
                "stop_loss": p.stop_loss,
                "meta": p.meta,
            }
            for p in db.query(ChartPattern).filter(ChartPattern.stock_id == stock_id).all()
        ],
    }


@router.get("/{stock_id}/support-resistance")
def get_sr(stock_id: int, db: Session = Depends(get_db)):
    levels = db.query(SupportResistance).filter(SupportResistance.stock_id == stock_id).all()
    if not levels:
        result = get_analysis_safe(db, stock_id)
        return result.get("support_resistance", [])
    return [
        {
            "level_type": l.level_type,
            "price": l.price,
            "strength": l.strength,
            "touches": l.touches,
            "meta": l.meta,
        }
        for l in levels
    ]


@router.get("/{stock_id}/prediction")
def get_prediction(stock_id: int, db: Session = Depends(get_db)):
    pred = (
        db.query(AIPrediction)
        .filter(AIPrediction.stock_id == stock_id)
        .order_by(AIPrediction.created_at.desc())
        .first()
    )
    if not pred:
        result = get_analysis_safe(db, stock_id)
        return result.get("prediction")
    return {
        "id": pred.id,
        "stock_id": pred.stock_id,
        "bullish_probability": pred.bullish_probability,
        "bearish_probability": pred.bearish_probability,
        "expected_direction": pred.expected_direction,
        "confidence": pred.confidence,
        "holding_period": pred.holding_period,
        "risk": pred.risk,
        "scores": pred.scores,
        "model_version": pred.model_version,
        "disclaimer": pred.disclaimer,
        "created_at": pred.created_at,
    }


@router.get("/{stock_id}/volume")
def get_volume(stock_id: int, db: Session = Depends(get_db)):
    df = get_price_dataframe(db, stock_id)
    if df.empty:
        raise HTTPException(status_code=404, detail="No price data")
    return analyze_volume(df)


def get_analysis_safe(db: Session, stock_id: int) -> dict:
    stock = db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return analyze_stock(db, stock, persist=True)
