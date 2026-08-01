"""Quick bootstrap: seed DB and download a subset of symbols."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.database.models import Stock, User
from app.services.analysis import analyze_stock
from app.services.data_downloader import download_stock_data, seed_stocks

PRIORITY = {
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "SBIN.NS",
    "^NSEI",
    "AAPL",
    "MSFT",
}


def main():
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.default_admin_email).first():
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
            print("Admin created")

        print("Seeding stocks…", seed_stocks(db))
        stocks = db.query(Stock).filter(Stock.symbol.in_(PRIORITY)).all()
        for i, stock in enumerate(stocks, 1):
            print(f"[{i}/{len(stocks)}] {stock.symbol}")
            try:
                print(" ", download_stock_data(db, stock, period="2y"))
                analyze_stock(db, stock, persist=True)
                print("  analyzed")
            except Exception as exc:
                print("  ERR", exc)
        print("Done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
