# Stock Market Analytics & Pattern Detection Platform

**signal-forge** — stock analytics personal portfolio

AI-powered analytics platform for historical market data, technical indicators, chart/candlestick patterns, support & resistance, volume analytics, probability scoring, scanning, watchlists, alerts, backtesting, portfolio tracking, and reports.

**Important:** This application does **not** guarantee future prices or profits. It provides statistical analysis and historical pattern matching only — not financial advice.

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SQLAlchemy, Pandas, NumPy, scikit-learn, XGBoost, APScheduler |
| Frontend | React, Vite, Tailwind CSS, TradingView Lightweight Charts |
| Data | Yahoo Finance (`yfinance`) — NSE/BSE/US |
| Auth | JWT access + refresh tokens |
| DB (dev) | SQLite (`data/stock_analytics.db`) |
| DB (prod) | PostgreSQL via `DATABASE_URL` |

## Quick start

### 1. Backend

```bash
cd backend
py -m pip install -r requirements.txt
py bootstrap.py          # seed stocks, download history, run analysis
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://127.0.0.1:8000/docs

Default admin:

- Email: `admin@signalforge.app`
- Password: `Admin@12345`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://127.0.0.1:5173

## Modules delivered

- Authentication (register, login, refresh, profile, change/forgot/reset password)
- Stock database + historical OHLCV downloader (daily/weekly/monthly)
- Technical indicator engine (SMA, EMA, RSI, MACD, ADX, ATR, VWAP, SuperTrend, Bollinger, Ichimoku, Fib, pivots, OBV, CCI, ROC, Williams %R, Momentum)
- Candlestick + chart pattern detection
- Support & resistance
- Volume analytics
- AI probability scoring (Random Forest + Logistic + XGBoost ensemble, heuristic fallback)
- Stock scanner
- Watchlist, alerts, portfolio
- Backtesting engine
- Dashboard, stock detail, reports (PDF/Excel)
- Daily next-session stock suggestions (min 10) + system options
- Admin panel + daily scheduler

## Environment

Copy `backend/.env.example` to `backend/.env` and adjust as needed.

## Deploy on Render

See [docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md). Blueprint file: `render.yaml` (API + static frontend + Postgres).

**Important (persistence):** Free web services have an ephemeral disk. SQLite files are wiped on every restart/redeploy.
Production must set `DATABASE_URL` to Render Postgres (or Neon/Supabase). Check `/api/health` — it should report `"database": "postgresql"` and `"persistent": true`.
