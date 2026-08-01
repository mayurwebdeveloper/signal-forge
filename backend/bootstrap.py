"""Bootstrap script: seed stocks, download history, run analysis."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.database.models import User
from app.services.analysis import analyze_stock
from app.services.data_downloader import download_stock_data, seed_stocks


def main():
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.default_admin_email).first()
        if not admin:
            db.add(
                User(
                    email=settings.default_admin_email,
                    username="admin",
                    full_name="Platform Admin",
                    hashed_password=hash_password(settings.default_admin_password),
                    is_admin=True,
                )
            )
            db.commit()
            print("Admin created:", settings.default_admin_email)

        added = seed_stocks(db)
        print(f"Seeded {added} new stocks")
        stocks = db.query(__import__("app.database.models", fromlist=["Stock"]).Stock).all()
        for i, stock in enumerate(stocks, 1):
            print(f"[{i}/{len(stocks)}] Downloading {stock.symbol}...")
            try:
                result = download_stock_data(db, stock, period="5y")
                print(f"  -> {result}")
                analyze_stock(db, stock, persist=True)
                print(f"  -> analyzed")
            except Exception as exc:
                print(f"  !! {exc}")
        print("Bootstrap complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
