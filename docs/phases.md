# Phases

## Phase 0 — Project Scaffold ✓ COMPLETE
Goal: Initialize repo and tooling
Deliverables: Project structure, CI/CD, basic API
Success: App runs locally
Built: FastAPI backend, React/Vite frontend, Docker Compose (postgres, redis, minio, backend, worker, frontend), GitHub Actions CI, structlog, Pydantic settings

## Phase 1 — Ingestion ✓ COMPLETE
Goal: Secure bundle upload
Deliverables: Upload, validation, storage
Success: End-to-end ingestion works
Built: POST /api/v1/bundles (multipart, size validation, S3 upload), GET list/detail endpoints, tenant isolation via X-Tenant-ID header, Celery task dispatch, Bundle model + migrations scaffold

## Phase 2 — Parsing ✓ COMPLETE
Goal: Structured evidence
Deliverables: Parsers, normalization
Success: Reliable structured data
Built: Evidence model (JSONB), alembic migration, BundleExtractor (tar.gz→tempdir), parsers for cluster-info/nodes/version, cluster-resources (all k8s kinds + Lists), pod-logs (tail-500, 10MB limit), host-collectors; run_all_parsers registry; GET /api/v1/bundles/{id}/evidence endpoint; 25 tests passing

## Phase 3 — Detection ✓ COMPLETE
Goal: Baseline diagnosis
Deliverables: Rules engine, findings
Success: Evidence-backed output
Built: Finding model, alembic migration 0002, 8 detection rules (node_not_ready, pod_crashloop, oom_killed, image_pull_error, pod_pending, pvc_pending, warning_events, resource_quota), run_all_rules registry, GET+PATCH /api/v1/bundles/{id}/findings, Celery task now runs rules after parsing; 55 tests passing

## Phase 4 — AI Assistance ✓ COMPLETE
Goal: Improve coverage
Deliverables: Retrieval + AI explanations
Success: Improved quality
Built: Anthropic client wrapper, prompt templates, explain_finding() service, POST /api/v1/bundles/{id}/findings/{id}/explain, AI_ENABLED/ANTHROPIC_API_KEY/AI_MODEL config, graceful 503 when disabled

## Phase 5 — Review & Reporting ✓ COMPLETE
Goal: Usable workflows
Deliverables: UI, reports, feedback
Success: Full support workflow
Built: build_report() JSON + build_markdown_report(), GET /api/v1/bundles/{id}/report + /report.md (attachment), frontend FindingCard with severity/status badges + Acknowledge/Resolve/Reopen + AI explanation collapsible + reviewer notes, BundleDetail findings grouped by severity, markdown report download button

## Phase 6 — Hardening ✓ COMPLETE
Goal: Enterprise readiness
Deliverables: Scaling, security, ops
Success: Production-ready system
Built: RequestIDMiddleware (X-Request-ID header + structlog binding), AccessLogMiddleware (method/path/status/duration), magic byte validation (gzip/zip), filename sanitization (path traversal + unsafe chars), slowapi rate limiting (upload 10/min, AI explain 20/min), /health/live + /health/ready (DB+Redis+S3 checks), DELETE /api/v1/bundles/{id} with S3 cleanup, Celery soft/hard time limits (540s/600s) + stuck-bundle cleanup beat task (5min), configurable CORS origins, DB pool settings, non-root Docker user + HEALTHCHECK, Celery beat service in Docker Compose, resource limits on worker (1g/1CPU) and backend (512m/0.5CPU), frontend ErrorBoundary, upload progress bar (XHR); 71 tests passing
