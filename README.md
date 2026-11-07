# Elite Portal

Elite Batch learning, assessment, daily-task and points portal for Francis Xavier Engineering College.

## Stack

- Backend: FastAPI + Uvicorn (ASGI), SQLAlchemy 2, Alembic migrations
- Database: PostgreSQL (Neon) in production; SQLite only for local development and tests
- Frontend: React 18 + Vite + TypeScript + Tailwind (`frontend/`)
- File storage: Cloudflare R2 (S3-compatible); local disk fallback for development only

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then fill in values
```

Without `DATABASE_URL`, the app uses `instance/elite_portal.sqlite3` (development only).

```powershell
python -m app.cli db-upgrade   # apply migrations
python -m app.cli seed-all     # admin (admin@elite.edu, password from ADMIN_PASSWORD) + 4 domains
python main.py                 # API on http://127.0.0.1:5000 (auto-reload)
```

Frontend (separate terminal):

```powershell
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api to :5000
```

If `frontend/dist` exists (`npm run build`), the backend also serves the SPA at `http://127.0.0.1:5000/`.

## Management commands

```powershell
python -m app.cli db-upgrade [revision]
python -m app.cli db-downgrade <revision>
python -m app.cli db-current
python -m app.cli seed-all | seed-domains
python -m app.cli create-admin EMAIL [--name N]
python -m app.cli create-coordinator EMAIL DOMAIN_CODE [--name N]
python -m app.cli create-faculty EMAIL DOMAIN_CODE [--name N]
python -m app.cli reset-admin-password EMAIL
```

Passwords are prompted for when `--password` is omitted. New migrations:
`alembic -c migrations/alembic.ini revision --autogenerate -m "describe change"`
(run from the repo root with `DATABASE_URL` set).

## Tests

```powershell
python -m pytest              # always runs against a throwaway SQLite database
cd frontend; npm run build    # type check + production build
```

## Health checks

- `GET /health` (and `/api/v1/health`): liveness plus database status
- `GET /ready` (and `/api/v1/ready`): 200 when the database is reachable, 503 otherwise

## Deployment (Render)

`render.yaml` defines the service:

- Build: `pip install -r requirements.txt`
- Pre-deploy: `python -m app.cli db-upgrade`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips "*"`
- Health check: `/ready`

Required environment variables: `APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL`
(with `sslmode=require`), `CORS_ORIGINS` / `FRONTEND_URL`, and the `R2_*` keys for durable uploads.
Optional: `MAIL_*` (password reset email) and `ROSTER_*` (approved-student roster). See `.env.example`.

The frontend is built with `VITE_API_URL` pointing at the API (`/api/v1` when served from the same origin).
If the frontend is on a different site than the API, set `SESSION_COOKIE_SAMESITE=none` (HTTPS required).

## Approved-student roster (optional)

Set `ROSTER_APPS_SCRIPT_URL` and `ROSTER_SHARED_SECRET` to require students to be on the approved roster
before registering. The Apps Script request/response contract is documented in `app/services/roster.py`.
When the roster is enabled and unreachable, registration is refused (fails closed).

## Rollback

1. Redeploy the previous release (or `git checkout checkpoint-pre-audit-2026-10-29` for the pre-migration code).
2. Only the `c3d5e7f9a1b2` migration (unique register-number index) is new; to revert it:
   `python -m app.cli db-downgrade 5b8f1d2a4e90`. It drops only that index; no data is touched.
3. Existing sessions stay valid across the rollback (same signing key and token format).
