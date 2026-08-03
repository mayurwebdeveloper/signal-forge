"""APScheduler daily jobs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.database.models import AuditLog, Job, Stock
from app.services.analysis import analyze_stock
from app.services.data_downloader import download_stock_data, seed_stocks
from app.services.suggestions import generate_daily_suggestions

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")


def _start_job(db: Session, job_type: str) -> Job:
    job = Job(job_type=job_type, status="running", started_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _finish_job(db: Session, job: Job, status: str, message: str, meta: dict | None = None):
    job.status = status
    job.message = message
    job.meta = meta
    job.finished_at = datetime.utcnow()
    db.commit()


def daily_pipeline():
    db = SessionLocal()
    job = _start_job(db, "daily_pipeline")
    try:
        seed_stocks(db)
        stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
        downloaded = analyzed = 0
        errors = []
        for stock in stocks:
            try:
                download_stock_data(db, stock, period="6mo")
                downloaded += 1
                analyze_stock(db, stock, persist=True)
                analyzed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": stock.symbol, "error": str(exc)})
                logger.exception("Pipeline failed for %s", stock.symbol)

        suggestions = generate_daily_suggestions(db, force=True)

        # Clean old logs (>30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        deleted = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
        db.commit()

        _finish_job(
            db,
            job,
            "success",
            f"Downloaded {downloaded}, analyzed {analyzed}, suggestions {suggestions.get('count', 0)}, cleaned {deleted} logs",
            {"errors": errors[:20], "suggestions": suggestions},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Daily pipeline failed")
        _finish_job(db, job, "failed", str(exc))
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(daily_pipeline, "cron", hour=18, minute=30, id="daily_pipeline", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
