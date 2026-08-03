"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, market, stocks
from app.core.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.database.models import User
from app.scheduler.jobs import shutdown_scheduler, start_scheduler
from app.services.data_downloader import seed_stocks
from app.services.suggestions import ensure_default_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


def ensure_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.default_admin_email).first()
        if not admin:
            admin = User(
                email=settings.default_admin_email,
                username="admin",
                full_name="Platform Admin",
                hashed_password=hash_password(settings.default_admin_password),
                is_admin=True,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin created: %s", settings.default_admin_email)
        seed_stocks(db)
        ensure_default_settings(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_admin()
    if settings.scheduler_enabled:
        try:
            start_scheduler()
        except Exception:
            logger.exception("Scheduler failed to start")
    yield
    shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered Stock Market Analytics & Pattern Detection Platform. "
        "Provides statistical analysis and historical pattern matching. "
        "Does not guarantee future prices or profits."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "error": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.app_version, "app": settings.app_name}


app.include_router(auth.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(market.dashboard_router, prefix="/api")
app.include_router(market.scanner_router, prefix="/api")
app.include_router(market.suggestions_router, prefix="/api")
app.include_router(market.watchlist_router, prefix="/api")
app.include_router(market.alerts_router, prefix="/api")
app.include_router(market.portfolio_router, prefix="/api")
app.include_router(market.backtest_router, prefix="/api")
app.include_router(market.reports_router, prefix="/api")
app.include_router(market.admin_router, prefix="/api")
