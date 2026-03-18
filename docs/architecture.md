# Architecture

## System Overview
Pipeline-based system for bundle analysis.

## Components
- **Frontend** — React 18/Vite/Tailwind, served via nginx (port 3000); BundleList, BundleDetail, FindingCard, upload flow
- **API & Orchestration** — FastAPI on port 8000; routes: /health, /api/v1/bundles, /api/v1/bundles/{id}/evidence, /api/v1/bundles/{id}/findings, /api/v1/bundles/{id}/report
- **Processing Pipeline** — Celery workers consuming Redis queue; pipeline: extract → parse → detect (rules) → store findings
- **Detection Engine** — 8 rules in app/detection/rules/; BaseRule ABC; run_all_rules registry; fires after parsing
- **AI Layer** — Anthropic client in app/ai/; explain_finding() service; POST /findings/{id}/explain; gated by AI_ENABLED flag
- **Reporting** — app/reporting/report.py; JSON + Markdown report generation; GET /report and /report.md
- **Storage** — MinIO (S3-compatible) for bundle files; PostgreSQL for metadata, evidence (JSONB), findings

## Data Flow
Upload → Extract → Parse → Detect → Report → Review → Store knowledge

## External Services
- Object storage
- Database
- AI model services

## Security & Ops Layer (Phase 6)
- **Request ID middleware** — UUID per request, X-Request-ID header, structlog context binding
- **Access log middleware** — structured HTTP logs with method, path, status, duration, tenant
- **Rate limiting** — slowapi on upload (10/min) and AI explain (20/min) per IP
- **Input validation** — magic byte check (gzip/zip), filename sanitization (path traversal + unsafe chars)
- **Health probes** — /health/live (liveness), /health/ready (DB + Redis + S3)
- **Bundle deletion** — DELETE /api/v1/bundles/{id} cleans S3 + DB (cascade)
- **Celery hardening** — soft_time_limit=540s, time_limit=600s, cleanup beat task for stuck bundles
- **Docker** — non-root appuser, HEALTHCHECK, resource limits, dedicated beat service

## Key Constraints
- Offline compatibility
- Security and isolation
