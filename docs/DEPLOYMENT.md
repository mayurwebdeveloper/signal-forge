# Deployment Guide

## Local development

1. Install Python 3.12+ and Node 20+.
2. Backend: `py -m pip install -r backend/requirements.txt`
3. Bootstrap data: `cd backend && py bootstrap.py`
4. API: `py -m uvicorn app.main:app --reload --port 8000`
5. Frontend: `cd frontend && npm install && npm run dev`

## Production (Railway / Render / VPS)

### Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Long random JWT secret |
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `DEFAULT_ADMIN_EMAIL` | Bootstrap admin email |
| `DEFAULT_ADMIN_PASSWORD` | Bootstrap admin password |
| `SCHEDULER_ENABLED` | `true` / `false` |
| `DEBUG` | `false` in production |

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend

```bash
cd frontend
npm ci
npm run build
# Serve `dist/` via nginx/CDN; set VITE_API_URL to the API origin at build time
```

### HTTPS

Terminate TLS at the reverse proxy (nginx, Caddy, Railway/Render edge). Never expose the API without HTTPS in production.

### PostgreSQL

Set `DATABASE_URL` before first start. SQLAlchemy will create tables on startup via `init_db()`.

### Scheduled jobs

APScheduler runs the daily pipeline at 18:30 UTC (download → indicators → patterns → AI predictions → log cleanup). Disable with `SCHEDULER_ENABLED=false` if using an external cron.
