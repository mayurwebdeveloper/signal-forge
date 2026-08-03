"""Dashboard, scanner, watchlist, alerts, portfolio, backtest, reports, admin APIs."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.backtesting.engine import STRATEGIES, run_backtest
from app.core.deps import get_current_admin, get_current_user
from app.database import get_db
from app.database.models import (
    AIPrediction,
    Alert,
    AlertNotification,
    AuditLog,
    Backtest,
    Job,
    Portfolio,
    PortfolioHolding,
    Report,
    Stock,
    User,
    Watchlist,
    WatchlistItem,
)
from app.database.schemas import (
    AlertCreate,
    AlertOut,
    BacktestOut,
    BacktestRequest,
    HoldingCreate,
    MessageOut,
    PortfolioCreate,
    PortfolioOut,
    ReportRequest,
    ScannerFilters,
    SystemSettingsOut,
    SystemSettingsUpdate,
    WatchlistCreate,
    WatchlistItemAdd,
    WatchlistOut,
    UserOut,
)
from app.scheduler.jobs import daily_pipeline
from app.services.analysis import analyze_stock, scan_stocks
from app.services.data_downloader import download_stock_data, get_price_dataframe, seed_stocks
from app.services.reports import generate_excel_report, generate_portfolio_pdf, generate_stock_pdf
from app.services.suggestions import (
    generate_daily_suggestions,
    get_suggestion_settings,
    list_daily_suggestions,
    update_suggestion_settings,
)

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
scanner_router = APIRouter(prefix="/scanner", tags=["Scanner"])
suggestions_router = APIRouter(prefix="/suggestions", tags=["Suggestions"])
watchlist_router = APIRouter(prefix="/watchlists", tags=["Watchlists"])
alerts_router = APIRouter(prefix="/alerts", tags=["Alerts"])
portfolio_router = APIRouter(prefix="/portfolios", tags=["Portfolio"])
backtest_router = APIRouter(prefix="/backtests", tags=["Backtesting"])
reports_router = APIRouter(prefix="/reports", tags=["Reports"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@dashboard_router.get("/overview")
def dashboard_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    movers = []
    for stock in stocks:
        df = get_price_dataframe(db, stock.id)
        if df.empty or len(df) < 2:
            continue
        change = float(df["close"].pct_change().iloc[-1] * 100)
        movers.append(
            {
                "stock_id": stock.id,
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "price": round(float(df["close"].iloc[-1]), 4),
                "change_pct": round(change, 3),
                "volume": float(df["volume"].iloc[-1]),
                "sector": stock.sector,
            }
        )
    movers.sort(key=lambda x: x["change_pct"], reverse=True)
    gainers = movers[:5]
    losers = sorted(movers, key=lambda x: x["change_pct"])[:5]

    preds = (
        db.query(AIPrediction)
        .order_by(AIPrediction.created_at.desc())
        .limit(50)
        .all()
    )
    seen = set()
    recommendations = []
    for p in preds:
        if p.stock_id in seen:
            continue
        seen.add(p.stock_id)
        stock = db.get(Stock, p.stock_id)
        if not stock:
            continue
        recommendations.append(
            {
                "stock_id": p.stock_id,
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "bullish_probability": p.bullish_probability,
                "expected_direction": p.expected_direction,
                "confidence": p.confidence,
                "risk": p.risk,
            }
        )
        if len(recommendations) >= 8:
            break

    # Signals from recent predictions / patterns
    signals = [r for r in recommendations if r["expected_direction"] in ("Bullish", "Bearish")][:10]

    # Watchlist snapshot
    wl = db.query(Watchlist).filter(Watchlist.user_id == user.id).first()
    watchlist_items = []
    if wl:
        for item in db.query(WatchlistItem).options(joinedload(WatchlistItem.stock)).filter(WatchlistItem.watchlist_id == wl.id).all():
            df = get_price_dataframe(db, item.stock_id)
            price = float(df["close"].iloc[-1]) if not df.empty else None
            chg = float(df["close"].pct_change().iloc[-1] * 100) if not df.empty and len(df) > 1 else None
            watchlist_items.append(
                {
                    "stock_id": item.stock_id,
                    "symbol": item.stock.symbol,
                    "company_name": item.stock.company_name,
                    "price": round(price, 4) if price else None,
                    "change_pct": round(chg, 3) if chg is not None else None,
                }
            )

    upcoming_breakouts = [m for m in movers if m["change_pct"] > 1.5][:5]

    market_change = 0.0
    if movers:
        market_change = round(sum(m["change_pct"] for m in movers) / len(movers), 3)

    daily = list_daily_suggestions(db, auto_generate=True)
    daily_picks = daily.get("suggestions", [])[:10]

    return {
        "market_overview": {
            "stocks_tracked": len(stocks),
            "avg_change_pct": market_change,
            "bullish_count": sum(1 for r in recommendations if r["expected_direction"] == "Bullish"),
            "bearish_count": sum(1 for r in recommendations if r["expected_direction"] == "Bearish"),
        },
        "top_gainers": gainers,
        "top_losers": losers,
        "watchlist": watchlist_items,
        "todays_signals": signals,
        "ai_recommendations": recommendations,
        "daily_suggestions": daily_picks,
        "suggestions_enabled": daily.get("enabled", True),
        "suggestions_date": daily.get("date"),
        "upcoming_breakouts": upcoming_breakouts,
        "disclaimer": "Statistical analysis only. Not financial advice. No guarantee of future prices or profits.",
    }


@scanner_router.post("/scan")
def run_scanner(filters: ScannerFilters, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = scan_stocks(db, filters)
    return {"results": results, "count": len(results)}


@suggestions_router.get("/daily")
def get_daily_suggestions(
    suggestion_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_daily_suggestions(db, for_date=suggestion_date, auto_generate=True)


@suggestions_router.post("/daily/refresh")
def refresh_daily_suggestions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = generate_daily_suggestions(db, force=True)
    payload = list_daily_suggestions(
        db,
        for_date=date.fromisoformat(result["date"]) if result.get("date") else None,
        auto_generate=False,
    )
    payload["refresh"] = result
    return payload


# ---------- Watchlists ----------
@watchlist_router.get("", response_model=list[WatchlistOut])
def list_watchlists(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wls = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.items).joinedload(WatchlistItem.stock))
        .filter(Watchlist.user_id == user.id)
        .all()
    )
    return wls


@watchlist_router.post("", response_model=WatchlistOut, status_code=201)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wl = Watchlist(user_id=user.id, name=payload.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


@watchlist_router.post("/{watchlist_id}/items", response_model=WatchlistOut)
def add_item(
    watchlist_id: int,
    payload: WatchlistItemAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    if not db.get(Stock, payload.stock_id):
        raise HTTPException(status_code=404, detail="Stock not found")
    exists = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.stock_id == payload.stock_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Stock already in watchlist")
    db.add(WatchlistItem(watchlist_id=watchlist_id, stock_id=payload.stock_id, notes=payload.notes))
    db.commit()
    return (
        db.query(Watchlist)
        .options(joinedload(Watchlist.items).joinedload(WatchlistItem.stock))
        .filter(Watchlist.id == watchlist_id)
        .first()
    )


@watchlist_router.delete("/{watchlist_id}/items/{item_id}", response_model=MessageOut)
def remove_item(watchlist_id: int, item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.watchlist_id == watchlist_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return MessageOut(message="Removed from watchlist")


# ---------- Alerts ----------
@alerts_router.get("", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).all()


@alerts_router.get("/notifications")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alerts = db.query(Alert).filter(Alert.user_id == user.id).all()
    alert_ids = [a.id for a in alerts]
    if not alert_ids:
        return []
    notes = (
        db.query(AlertNotification)
        .filter(AlertNotification.alert_id.in_(alert_ids))
        .order_by(AlertNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {"id": n.id, "alert_id": n.alert_id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at}
        for n in notes
    ]


@alerts_router.post("", response_model=AlertOut, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = Alert(
        user_id=user.id,
        stock_id=payload.stock_id,
        alert_type=payload.alert_type,
        condition=payload.condition,
        channel=payload.channel,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@alerts_router.delete("/{alert_id}", response_model=MessageOut)
def delete_alert(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
    return MessageOut(message="Alert deleted")


# ---------- Portfolio ----------
def _enrich_portfolio(db: Session, portfolio: Portfolio) -> dict:
    holdings_out = []
    total_inv = total_val = 0.0
    sector_map: dict[str, float] = defaultdict(float)
    for h in portfolio.holdings:
        df = get_price_dataframe(db, h.stock_id)
        price = float(df["close"].iloc[-1]) if not df.empty else h.avg_buy_price
        mv = price * h.quantity
        inv = h.avg_buy_price * h.quantity
        pnl = mv - inv
        pnl_pct = (pnl / inv * 100) if inv else 0
        total_inv += inv
        total_val += mv
        sector = h.stock.sector or "Other"
        sector_map[sector] += mv
        holdings_out.append(
            {
                "id": h.id,
                "stock_id": h.stock_id,
                "quantity": h.quantity,
                "avg_buy_price": h.avg_buy_price,
                "buy_date": h.buy_date,
                "notes": h.notes,
                "stock": {
                    "id": h.stock.id,
                    "symbol": h.stock.symbol,
                    "company_name": h.stock.company_name,
                    "exchange": h.stock.exchange,
                    "sector": h.stock.sector,
                    "industry": h.stock.industry,
                    "isin": h.stock.isin,
                    "market_cap": h.stock.market_cap,
                    "currency": h.stock.currency,
                    "is_active": h.stock.is_active,
                    "last_updated": h.stock.last_updated,
                },
                "current_price": round(price, 4),
                "market_value": round(mv, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 3),
            }
        )
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "created_at": portfolio.created_at,
        "holdings": holdings_out,
        "total_investment": round(total_inv, 2),
        "total_value": round(total_val, 2),
        "total_pnl": round(total_val - total_inv, 2),
        "total_return_pct": round((total_val - total_inv) / total_inv * 100, 3) if total_inv else 0,
        "sector_allocation": {k: round(v, 2) for k, v in sector_map.items()},
    }


@portfolio_router.get("")
def list_portfolios(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    portfolios = (
        db.query(Portfolio)
        .options(joinedload(Portfolio.holdings).joinedload(PortfolioHolding.stock))
        .filter(Portfolio.user_id == user.id)
        .all()
    )
    return [_enrich_portfolio(db, p) for p in portfolios]


@portfolio_router.post("", status_code=201)
def create_portfolio(payload: PortfolioCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = Portfolio(user_id=user.id, name=payload.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _enrich_portfolio(db, p)


@portfolio_router.post("/{portfolio_id}/holdings")
def add_holding(
    portfolio_id: int,
    payload: HoldingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if not db.get(Stock, payload.stock_id):
        raise HTTPException(status_code=404, detail="Stock not found")
    db.add(
        PortfolioHolding(
            portfolio_id=portfolio_id,
            stock_id=payload.stock_id,
            quantity=payload.quantity,
            avg_buy_price=payload.avg_buy_price,
            buy_date=payload.buy_date,
            notes=payload.notes,
        )
    )
    db.commit()
    p = (
        db.query(Portfolio)
        .options(joinedload(Portfolio.holdings).joinedload(PortfolioHolding.stock))
        .filter(Portfolio.id == portfolio_id)
        .first()
    )
    return _enrich_portfolio(db, p)


@portfolio_router.delete("/{portfolio_id}/holdings/{holding_id}", response_model=MessageOut)
def delete_holding(
    portfolio_id: int,
    holding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    h = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.id == holding_id, PortfolioHolding.portfolio_id == portfolio_id)
        .first()
    )
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()
    return MessageOut(message="Holding removed")


# ---------- Backtests ----------
@backtest_router.get("/strategies")
def list_strategies():
    return [{"id": k, "name": v} for k, v in STRATEGIES.items()]


@backtest_router.post("", response_model=BacktestOut)
def create_backtest(payload: BacktestRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stock = db.get(Stock, payload.stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    df = get_price_dataframe(db, stock.id)
    if df.empty:
        raise HTTPException(status_code=400, detail="No price data. Download first.")
    mask = (df.index.date >= payload.start_date) & (df.index.date <= payload.end_date)
    window = df.loc[mask]
    if len(window) < 30:
        raise HTTPException(status_code=400, detail="Not enough bars in selected date range")
    results, trades = run_backtest(window, payload.strategy, payload.capital, payload.params)
    bt = Backtest(
        user_id=user.id,
        stock_id=stock.id,
        strategy=payload.strategy,
        start_date=payload.start_date,
        end_date=payload.end_date,
        capital=payload.capital,
        results=results,
        trades=trades,
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)
    return bt


@backtest_router.get("", response_model=list[BacktestOut])
def list_backtests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Backtest).filter(Backtest.user_id == user.id).order_by(Backtest.created_at.desc()).limit(50).all()


@backtest_router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bt = db.query(Backtest).filter(Backtest.id == backtest_id, Backtest.user_id == user.id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return bt


# ---------- Reports ----------
@reports_router.post("")
def create_report(payload: ReportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    path = None
    title = "Report"
    if payload.report_type == "stock_analysis":
        if not payload.stock_id:
            raise HTTPException(status_code=400, detail="stock_id required")
        stock = db.get(Stock, payload.stock_id)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        analysis = analyze_stock(db, stock, persist=False)
        title = f"Stock Analysis — {stock.symbol}"
        if payload.format == "excel":
            path = generate_excel_report(title, [{"metric": k, "value": str(v)} for k, v in (analysis.get("prediction") or {}).items()], "stock")
        else:
            path = generate_stock_pdf(title, analysis)
    elif payload.report_type == "portfolio":
        if not payload.portfolio_id:
            raise HTTPException(status_code=400, detail="portfolio_id required")
        p = (
            db.query(Portfolio)
            .options(joinedload(Portfolio.holdings).joinedload(PortfolioHolding.stock))
            .filter(Portfolio.id == payload.portfolio_id, Portfolio.user_id == user.id)
            .first()
        )
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        data = _enrich_portfolio(db, p)
        title = f"Portfolio Report — {p.name}"
        path = generate_portfolio_pdf(title, data) if payload.format == "pdf" else generate_excel_report(title, data["holdings"], "portfolio")
    elif payload.report_type == "strategy":
        if not payload.backtest_id:
            raise HTTPException(status_code=400, detail="backtest_id required")
        bt = db.query(Backtest).filter(Backtest.id == payload.backtest_id, Backtest.user_id == user.id).first()
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        title = f"Strategy Report — {bt.strategy}"
        rows = [{"metric": k, "value": str(v)} for k, v in (bt.results or {}).items() if k != "equity_curve"]
        path = generate_excel_report(title, rows, "strategy") if payload.format == "excel" else generate_excel_report(title, rows, "strategy")
    else:
        title = "Performance Report"
        stocks = db.query(Stock).filter(Stock.is_active == True).limit(50).all()  # noqa: E712
        rows = []
        for s in stocks:
            df = get_price_dataframe(db, s.id)
            if df.empty:
                continue
            rows.append(
                {
                    "symbol": s.symbol,
                    "price": float(df["close"].iloc[-1]),
                    "change_pct": float(df["close"].pct_change().iloc[-1] * 100) if len(df) > 1 else 0,
                }
            )
        path = generate_excel_report(title, rows, "performance")

    report = Report(
        user_id=user.id,
        report_type=payload.report_type,
        title=title,
        file_path=path,
        format=payload.format,
        meta={"stock_id": payload.stock_id, "portfolio_id": payload.portfolio_id, "backtest_id": payload.backtest_id},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "title": report.title, "file_path": report.file_path, "format": report.format}


@reports_router.get("")
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reports = db.query(Report).filter(Report.user_id == user.id).order_by(Report.created_at.desc()).limit(50).all()
    return [
        {"id": r.id, "title": r.title, "report_type": r.report_type, "format": r.format, "created_at": r.created_at}
        for r in reports
    ]


@reports_router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id, Report.user_id == user.id).first()
    if not report or not report.file_path:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(report.file_path, filename=report.file_path.split("\\")[-1].split("/")[-1])


# ---------- Admin ----------
@admin_router.get("/users", response_model=list[UserOut])
def admin_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@admin_router.patch("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    user.is_active = not user.is_active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@admin_router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
    return [
        {
            "id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "message": j.message,
            "started_at": j.started_at,
            "finished_at": j.finished_at,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@admin_router.get("/logs")
def list_logs(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource": l.resource,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at,
        }
        for l in logs
    ]


@admin_router.post("/refresh-data", response_model=MessageOut)
def refresh_data(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    seed_stocks(db)
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    count = 0
    for stock in stocks:
        try:
            download_stock_data(db, stock, period="1y")
            analyze_stock(db, stock, persist=True)
            count += 1
        except Exception:
            continue
    suggestions = generate_daily_suggestions(db, force=True)
    return MessageOut(
        message=f"Refreshed {count} stocks and generated {suggestions.get('count', 0)} daily suggestions"
    )


@admin_router.post("/run-pipeline", response_model=MessageOut)
def run_pipeline(admin: User = Depends(get_current_admin)):
    daily_pipeline()
    return MessageOut(message="Daily pipeline executed")


@admin_router.get("/stocks")
def admin_stocks(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return db.query(Stock).order_by(Stock.symbol).all()


@admin_router.get("/settings", response_model=SystemSettingsOut)
def get_system_settings(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return SystemSettingsOut(**get_suggestion_settings(db))


@admin_router.put("/settings", response_model=SystemSettingsOut)
def put_system_settings(
    payload: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    updated = update_suggestion_settings(db, payload.model_dump(exclude_unset=True))
    if updated["suggestions_min_count"] > updated["suggestions_max_count"]:
        update_suggestion_settings(db, {"suggestions_max_count": updated["suggestions_min_count"]})
        updated = get_suggestion_settings(db)
    return SystemSettingsOut(**updated)


@admin_router.post("/suggestions/regenerate", response_model=MessageOut)
def admin_regenerate_suggestions(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = generate_daily_suggestions(db, force=True)
    return MessageOut(
        message=f"Generated {result.get('count', 0)} suggestions for {result.get('date')}",
        detail=result,
    )
