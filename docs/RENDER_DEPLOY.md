# Deploy Signal Forge on Render

This repo includes a [Render Blueprint](https://render.com/docs/infrastructure-as-code) at `/render.yaml`.

## Prerequisites

- GitHub repo connected (this project: `mayurwebdeveloper/signal-forge`)
- A Render account: https://dashboard.render.com
- A paid Postgres plan is required (`basic-256mb` in the blueprint). Free web/static tiers still sleep after idle time.

## One-click Blueprint deploy

1. Push the latest code to GitHub `main`.
2. Open **https://dashboard.render.com/select-repo?type=blueprint**
3. Connect the `signal-forge` repository.
4. Render reads `render.yaml` and creates:
   - `signal-forge-db` (PostgreSQL)
   - `signal-forge-api` (FastAPI / Uvicorn)
   - `signal-forge-web` (React static site)
5. When prompted, set **`DEFAULT_ADMIN_PASSWORD`** (do not use the local default in production).
6. Apply / create the blueprint and wait for builds.

## After deploy

| Service | Typical URL |
|---------|-------------|
| API | `https://signal-forge-api.onrender.com` |
| Health | `https://signal-forge-api.onrender.com/api/health` |
| Frontend | `https://signal-forge-web.onrender.com` |
| API docs | `https://signal-forge-api.onrender.com/docs` |

1. Confirm API health returns `{"status":"ok",...}`.
2. On the API service → Environment, set `CORS_ORIGINS` to your exact frontend URL if it differs.
3. If the frontend URL or API URL differs from the blueprint defaults, update:
   - API: `CORS_ORIGINS`
   - Frontend: `VITE_API_URL` (then **Clear build cache & deploy**)
4. Open the frontend, log in with `DEFAULT_ADMIN_EMAIL` / your password.
5. Use **Admin → refresh data / run pipeline** so Yahoo history and models populate (first boot is empty).

## Notes

- Free web services spin down when idle; the first request can take ~30–60s.
- Disk is ephemeral: trained `.joblib` models are not durable across redeploys (heuristics/ML retrain on demand).
- SQLite is for local dev only; production uses `DATABASE_URL` from Render Postgres.
- Heavy pip installs (`xgboost`, `lightgbm`, `scikit-learn`) can take several minutes on first build.
