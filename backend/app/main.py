"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, market, stocks
from app.core.config import BASE_DIR, get_settings
from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.database.models import User
from app.scheduler.jobs import shutdown_scheduler, start_scheduler
from app.services.data_downloader import seed_stocks
from app.services.suggestions import ensure_default_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

# Prefer built assets copied into backend/static (Render single-service deploy).
# Fallback to frontend/dist for local full-stack builds.
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
SPA_DIR = STATIC_DIR if (STATIC_DIR / "index.html").exists() else FRONTEND_DIST


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
    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        dialect = "sqlite"
    elif "postgres" in db_url:
        dialect = "postgresql"
    else:
        dialect = "other"
    return {
        "status": "ok",
        "version": settings.app_version,
        "app": settings.app_name,
        "database": dialect,
        "persistent": dialect != "sqlite",
    }


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


def _mount_spa() -> None:
    """Serve the Vite React build from the same origin as the API."""
    if not (SPA_DIR / "index.html").exists():
        logger.warning("SPA build not found at %s — API-only mode", SPA_DIR)
        return

    assets = SPA_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def spa_index():
        return FileResponse(SPA_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Never shadow API / docs / OpenAPI
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = SPA_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(SPA_DIR / "index.html")

    logger.info("Serving SPA from %s", SPA_DIR)


_mount_spa()
