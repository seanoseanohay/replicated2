# Bundle Analyzer

AI-assisted Kubernetes support bundle analyzer for support engineers and ISV developers.

## Goals

- Automated ingestion and analysis of Kubernetes support bundles
- Evidence-backed diagnostic findings (rules + AI hybrid)

## Stack

- **Backend:** FastAPI (Python 3.11), async SQLAlchemy, Celery workers
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL 16
- **Storage:** MinIO (S3-compatible, supports air-gapped)
- **Queue:** Redis + Celery
- **Hosting:** Docker Compose (local), air-gapped compatible

## Local development

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minioadmin / minioadmin)

### Run backend tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

### Run DB migrations

```bash
cd backend
alembic upgrade head
```

## Project docs

See the `docs/` folder for requirements, scope, phases, architecture, decisions, constraints, and system-map.
