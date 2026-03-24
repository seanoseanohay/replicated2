# Bundle Analyzer

AI-assisted Kubernetes support bundle analyzer for support engineers and ISV developers.

## Goals

- Automated ingestion and analysis of Kubernetes support bundles
- Evidence-backed diagnostic findings (rules + AI hybrid)
- Collaborative review workflow with audit trail
- Multi-tenant, role-based access control

## Stack

- **Backend:** FastAPI (Python 3.11), async SQLAlchemy, Celery workers
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL 16
- **Storage:** MinIO (S3-compatible, supports air-gapped)
- **Queue:** Redis + Celery
- **Hosting:** Docker Compose (local), Railway (cloud), air-gapped compatible

## Features

- **Ingestion:** Upload `.tar.gz` support bundles with magic-byte validation, filename sanitization, and S3 storage
- **Parsing:** Structured evidence extraction — cluster-info, nodes, pod logs, host collectors, all Kubernetes resource kinds
- **Detection:** 19 detection rules covering node health, pod lifecycle, storage, capacity, and resource configuration
- **AI Assistance:** Anthropic-powered finding explanations with graceful degradation when disabled
- **Reporting:** JSON and Markdown reports with download
- **Authentication:** JWT-based login (access 60 min + refresh 30 days), role-based access (analyst / manager / admin)
- **Dashboard:** Aggregate health scores, per-bundle health bars, critical findings summary
- **Audit Trail:** Full history of status changes, AI explanations, and comments on each finding
- **Notifications:** Email (SMTP) and Slack alerts on critical/high findings, configurable per tenant
- **Comments:** Threaded discussion on findings; delete own comment or manager can delete any
- **Bundle Comparison:** Diff two bundles to see new/resolved/persisting findings
- **Admin:** Bootstrap admin account via env vars; admin panel for tenant management
- **Hardening:** Rate limiting (slowapi), request-ID tracing, access logs, health checks, Celery time limits, non-root Docker user

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

The test suite has 159 passing tests covering ingestion, parsing, detection, auth, dashboard, audit trail, comments, comparison, notifications, and admin routes.

### Run DB migrations

```bash
cd backend
alembic upgrade head
```

## Detection rules

| Rule | Severity |
|------|----------|
| Node not ready | critical |
| Pod crash loop | critical |
| OOM killed | critical |
| Image pull error | high |
| Init container failed | high |
| Warning event reasons (FailedScheduling, FailedMount, Evicted, BackOff) | high/medium |
| Pod pending | medium |
| PVC pending | medium |
| Resource quota near limit | medium |
| Node pressure (DiskPressure/MemoryPressure/PIDPressure) | medium |
| Deployment unavailable | medium |
| StatefulSet unavailable | medium |
| HPA at max replicas | medium |
| Warning events (general) | medium |
| DaemonSet unavailable | medium |
| Pod terminating stuck | medium |
| High restart count | low |
| Failed jobs | low |
| Missing resource limits | low |

## API endpoints (summary)

- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- `POST /api/v1/bundles` — upload bundle
- `GET /api/v1/bundles`, `GET /api/v1/bundles/{id}` — list / detail
- `POST /api/v1/bundles/{id}/reanalyze` — re-run detection rules on existing evidence
- `DELETE /api/v1/bundles/{id}` — delete (manager only)
- `GET /api/v1/bundles/{id}/evidence`
- `GET /api/v1/bundles/{id}/findings`, `PATCH /api/v1/bundles/{id}/findings/{id}`
- `POST /api/v1/bundles/{id}/findings/{id}/explain` — AI explanation
- `GET /api/v1/bundles/{id}/findings/{id}/events` — audit trail
- `GET/POST/DELETE /api/v1/bundles/{bundle_id}/findings/{finding_id}/comments`
- `GET /api/v1/bundles/{id}/report`, `GET /api/v1/bundles/{id}/report.md`
- `GET /api/v1/bundles/compare?bundle_a=...&bundle_b=...`
- `GET /api/v1/dashboard`
- `GET/POST /api/v1/notifications/config`
- `GET /health/live`, `GET /health/ready`
- `GET /api/v1/admin/users` — list all users (admin only)
- `PATCH /api/v1/admin/users/{id}/role` — change user role (admin only)
- `PATCH /api/v1/admin/users/{id}/status` — activate/deactivate user (admin only)
- `GET /api/v1/admin/stats` — system-wide counts (admin only)

## Project docs

See the `docs/` folder for requirements, scope, phases, architecture, decisions, and constraints.
