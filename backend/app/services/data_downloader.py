"""Historical data downloader using yfinance."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Stock, StockPrice

settings = get_settings()

# Seed universe — NSE majors + indices + a few US blue chips
DEFAULT_STOCKS = [
    {"symbol": "RELIANCE.NS", "company_name": "Reliance Industries", "exchange": "NSE", "sector": "Energy", "industry": "Oil & Gas"},
    {"symbol": "TCS.NS", "company_name": "Tata Consultancy Services", "exchange": "NSE", "sector": "Technology", "industry": "IT Services"},
    {"symbol": "INFY.NS", "company_name": "Infosys", "exchange": "NSE", "sector": "Technology", "industry": "IT Services"},
    {"symbol": "HDFCBANK.NS", "company_name": "HDFC Bank", "exchange": "NSE", "sector": "Financials", "industry": "Banks"},
    {"symbol": "ICICIBANK.NS", "company_name": "ICICI Bank", "exchange": "NSE", "sector": "Financials", "industry": "Banks"},
    {"symbol": "SBIN.NS", "company_name": "State Bank of India", "exchange": "NSE", "sector": "Financials", "industry": "Banks"},
    {"symbol": "BHARTIARTL.NS", "company_name": "Bharti Airtel", "exchange": "NSE", "sector": "Communication", "industry": "Telecom"},
    {"symbol": "ITC.NS", "company_name": "ITC Limited", "exchange": "NSE", "sector": "Consumer", "industry": "FMCG"},
    {"symbol": "LT.NS", "company_name": "Larsen & Toubro", "exchange": "NSE", "sector": "Industrials", "industry": "Engineering"},
    {"symbol": "AXISBANK.NS", "company_name": "Axis Bank", "exchange": "NSE", "sector": "Financials", "industry": "Banks"},
    {"symbol": "WIPRO.NS", "company_name": "Wipro", "exchange": "NSE", "sector": "Technology", "industry": "IT Services"},
    {"symbol": "MARUTI.NS", "company_name": "Maruti Suzuki", "exchange": "NSE", "sector": "Consumer", "industry": "Automobiles"},
    {"symbol": "SUNPHARMA.NS", "company_name": "Sun Pharmaceutical", "exchange": "NSE", "sector": "Healthcare", "industry": "Pharma"},
    {"symbol": "TMPV.NS", "company_name": "Tata Motors Passenger Vehicles", "exchange": "NSE", "sector": "Consumer", "industry": "Automobiles"},
    {"symbol": "ASIANPAINT.NS", "company_name": "Asian Paints", "exchange": "NSE", "sector": "Materials", "industry": "Paints"},
    {"symbol": "^NSEI", "company_name": "Nifty 50", "exchange": "NSE", "sector": "Index", "industry": "Index"},
    {"symbol": "^NSEBANK", "company_name": "Nifty Bank", "exchange": "NSE", "sector": "Index", "industry": "Index"},
    {"symbol": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Technology", "industry": "Consumer Electronics"},
    {"symbol": "MSFT", "company_name": "Microsoft Corp.", "exchange": "NASDAQ", "sector": "Technology", "industry": "Software"},
    {"symbol": "GOOGL", "company_name": "Alphabet Inc.", "exchange": "NASDAQ", "sector": "Technology", "industry": "Internet"},
]


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def fetch_history(
    symbol: str,
    period: str | None = None,
    interval: str = "1d",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    if start or end:
        df = ticker.history(start=start, end=end, interval=interval, auto_adjust=False)
    else:
        period = period or f"{settings.data_lookback_years}y"
        df = ticker.history(period=period, interval=interval, auto_adjust=False)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    # Normalize columns
    rename = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date
    df = df[["date", "open", "high", "low", "close", "adj_close", "volume"]].dropna()
    return df


def fetch_ticker_info(symbol: str) -> dict:
    try:
        info = yf.Ticker(symbol).info or {}
        return {
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency") or "INR",
            "exchange": info.get("exchange") or "NSE",
        }
    except Exception:
        return {"company_name": symbol}


def search_yahoo_symbols(query: str, limit: int = 12) -> list[dict]:
    """Search Yahoo Finance for symbols by company name or ticker."""
    q = (query or "").strip()
    if len(q) < 1:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    def add_item(symbol: str, name: str | None = None, exchange: str | None = None, quote_type: str | None = None):
        sym = normalize_symbol(symbol)
        if not sym or sym in seen:
            return
        seen.add(sym)
        results.append(
            {
                "symbol": sym,
                "company_name": name or sym,
                "exchange": exchange or "",
                "quote_type": quote_type or "",
            }
        )

    # Direct ticker probe (exact / with common suffixes)
    candidates = [q.upper()]
    if "." not in q.upper():
        candidates += [f"{q.upper()}.NS", f"{q.upper()}.BO", f"{q.upper()}.NS".replace(" ", "")]

    for cand in candidates:
        try:
            hist = yf.Ticker(cand).history(period="5d")
            if hist is not None and not hist.empty:
                info = fetch_ticker_info(cand)
                add_item(cand, info.get("company_name"), info.get("exchange"), "EQUITY")
        except Exception:
            continue

    # Yahoo text search
    try:
        search = yf.Search(q, max_results=limit)
        for quote in search.quotes or []:
            symbol = quote.get("symbol")
            if not symbol:
                continue
            add_item(
                symbol,
                quote.get("longname") or quote.get("shortname") or quote.get("longName") or quote.get("shortName"),
                quote.get("exchDisp") or quote.get("exchange"),
                quote.get("quoteType"),
            )
            if len(results) >= limit:
                break
    except Exception:
        pass

    return results[:limit]


def seed_stocks(db: Session) -> int:
    added = 0
    for item in DEFAULT_STOCKS:
        existing = db.query(Stock).filter(Stock.symbol == item["symbol"]).first()
        if existing:
            continue
        db.add(Stock(**item, currency="INR" if item["exchange"] == "NSE" else "USD"))
        added += 1
    db.commit()
    return added


def save_prices(db: Session, stock: Stock, df: pd.DataFrame, timeframe: str = "1d") -> int:
    if df.empty:
        return 0
    # Existing dates for upsert-lite
    existing_dates = {
        r.date
        for r in db.query(StockPrice.date)
        .filter(StockPrice.stock_id == stock.id, StockPrice.timeframe == timeframe)
        .all()
    }
    count = 0
    for _, row in df.iterrows():
        d = row["date"]
        if hasattr(d, "date"):
            d = d.date()
        if d in existing_dates:
            continue
        db.add(
            StockPrice(
                stock_id=stock.id,
                date=d,
                timeframe=timeframe,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adj_close=float(row["adj_close"]),
                volume=float(row["volume"]),
            )
        )
        count += 1
    stock.last_updated = datetime.utcnow()
    db.commit()
    return count


def download_stock_data(db: Session, stock: Stock, period: str | None = None) -> dict:
    df = fetch_history(stock.symbol, period=period, interval="1d")
    if df.empty:
        return {
            "symbol": stock.symbol,
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "rows": 0,
            "error": f"No price data from Yahoo Finance for {stock.symbol}. Symbol may be delisted or renamed.",
        }
    daily = save_prices(db, stock, df, "1d")

    # Weekly / Monthly resampled from daily
    weekly_count = monthly_count = 0
    if not df.empty:
        tmp = df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"])
        tmp = tmp.set_index("date")
        weekly = (
            tmp.resample("W")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "adj_close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )
        weekly["date"] = weekly["date"].dt.date
        weekly_count = save_prices(db, stock, weekly, "1wk")

        monthly = (
            tmp.resample("ME")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "adj_close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )
        monthly["date"] = monthly["date"].dt.date
        monthly_count = save_prices(db, stock, monthly, "1mo")

    # Refresh metadata
    info = fetch_ticker_info(stock.symbol)
    if info.get("market_cap"):
        stock.market_cap = info["market_cap"]
    if info.get("sector") and not stock.sector:
        stock.sector = info["sector"]
    if info.get("industry") and not stock.industry:
        stock.industry = info["industry"]
    db.commit()

    return {"symbol": stock.symbol, "daily": daily, "weekly": weekly_count, "monthly": monthly_count, "rows": len(df)}


def get_price_dataframe(db: Session, stock_id: int, timeframe: str = "1d", limit: int | None = None) -> pd.DataFrame:
    q = (
        db.query(StockPrice)
        .filter(StockPrice.stock_id == stock_id, StockPrice.timeframe == timeframe)
        .order_by(StockPrice.date.asc())
    )
    rows = q.all()
    if limit:
        rows = rows[-limit:]
    if not rows:
        return pd.DataFrame()
    data = [
        {
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "adj_close": r.adj_close,
            "volume": r.volume,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df
