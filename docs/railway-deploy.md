# Railway Deployment Guide

## Prerequisites
- Railway account (railway.app)
- Railway CLI: `npm install -g @railway/cli` then `railway login`
- Cloudflare account with R2 enabled
- GitHub repo connected to Railway

## 1. Create Cloudflare R2 Bucket

1. Go to Cloudflare dashboard → R2 → Create bucket → name it `bundles`
2. Go to R2 → Manage R2 API Tokens → Create API Token
   - Permissions: Object Read & Write on bucket `bundles`
   - Save: Account ID, Access Key ID, Secret Access Key
3. Your endpoint URL: `https://<account_id>.r2.cloudflarestorage.com`

## 2. Create Railway Project

1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select this repository

## 3. Add Managed Services

In the Railway project dashboard, click **+ New** and add:
- **PostgreSQL** (Railway managed) — copy `DATABASE_URL` from its Variables tab
- **Redis** (Railway managed) — copy `REDIS_URL` from its Variables tab

## 4. Create Services

Railway will auto-detect the repo. Create **4 services**:

### Backend (API)
- Source: this repo, Root Directory: `backend/`
- Railway will use `backend/railway.toml` automatically
- Start command (from railway.toml): `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Worker
- Source: this repo, Root Directory: `backend/`
- Override start command: `celery -A app.workers.tasks worker --loglevel=info --concurrency=2`

### Beat
- Source: this repo, Root Directory: `backend/`
- Override start command: `celery -A app.workers.tasks beat --loglevel=info`

### Frontend
- Source: this repo, Root Directory: `frontend/`
- Railway will use `frontend/railway.toml` automatically

## 5. Configure Environment Variables

### Backend, Worker, and Beat services — set these variables:
```
DATABASE_URL=<from Railway PostgreSQL addon>
REDIS_URL=<from Railway Redis addon>
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_ACCESS_KEY=<r2_access_key_id>
S3_SECRET_KEY=<r2_secret_access_key>
S3_BUCKET_NAME=bundles
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
APP_ENV=production
MAX_BUNDLE_SIZE_MB=500
CORS_ALLOWED_ORIGINS=https://<frontend-service>.railway.app
AI_ENABLED=false
ANTHROPIC_API_KEY=
AI_MODEL=claude-opus-4-6
DB_POOL_SIZE=5
DB_POOL_OVERFLOW=10
RATE_LIMIT_UPLOAD=10/minute
RATE_LIMIT_AI=20/minute
```

### Frontend service — set these build variables:
```
VITE_API_URL=https://<backend-service>.railway.app
PORT=3000
```

> Note: Set `VITE_API_URL` **before** the first deploy — it is baked into the JS bundle at build time.

## 6. Deploy

1. Push to `master` — Railway auto-deploys all services
2. Check deploy logs for each service:
   - Backend: should show `alembic upgrade head` then uvicorn startup
   - Worker: should show `[tasks.worker] ready`
   - Beat: should show `[beat] ready`
   - Frontend: nginx serving on PORT

## 7. Verify

- Backend health: `https://<backend>.railway.app/health/ready`
- Frontend: visit `https://<frontend>.railway.app`

## CORS Note

If you see CORS errors in the browser console, update `CORS_ALLOWED_ORIGINS` on the backend service to exactly match the frontend URL (no trailing slash).

## Rotating Secrets

To rotate `SECRET_KEY`: update the variable in Railway → redeploy backend, worker, beat.

## Database Migrations

Migrations run automatically on each backend deploy (`alembic upgrade head` in the start command). To run manually:
```bash
railway run --service backend alembic upgrade head
```
