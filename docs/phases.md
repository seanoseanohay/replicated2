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

## Phase 3.1 — Extended Detection (Warnings & Capacity) ✓ COMPLETE
Goal: Catch degraded-but-not-down cluster states
Deliverables: 5 new detection rules, updated registry, new tests
Success: Warning-level issues surface before they become critical
Built: node_pressure (DiskPressure/MemoryPressure/PIDPressure, medium), deployment_unavailable (availableReplicas < desiredReplicas, medium), statefulset_unavailable (readyReplicas < replicas, medium), hpa_maxed (HPA at maxReplicas, medium), warning_event_reasons (FailedScheduling/FailedMount/Evicted/BackOff grouped by reason, high/medium); 9 new tests; 81 tests passing

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

## Phase 7 — Authentication & Roles ✓ COMPLETE
Goal: Real user identity, not just X-Tenant-ID header
Deliverables: Login, JWT tokens, role-based access control
Success: Users log in; managers see more than analysts
Built: User model + alembic migration 0003 (email/tenant_id unique constraint), passlib[bcrypt] password hashing, python-jose JWT (access 60min + refresh 30d), POST /auth/register + /auth/login + /auth/refresh + GET /auth/me, get_tenant_id dep (JWT preferred, X-Tenant-ID fallback for backward compat), require_auth + require_manager deps, analyst blocked from resolving findings (403), DELETE /bundles requires manager role, frontend AuthContext (localStorage token, session restore via /auth/me), LoginPage (sign in / create account tabs, dark Tailwind card), Navbar (email + role badge + logout), App.tsx protected routes (redirect to /login if unauthenticated); 90 tests passing

## Phase 8 — Dashboard & Health Overview ✓ COMPLETE
Goal: At-a-glance cluster health across all bundles
Deliverables: Global dashboard, per-bundle health bar, aggregate stats
Success: Green means go, red means wake someone up
Built: GET /api/v1/dashboard (DashboardStats + BundleHealthSummary schemas, compute_health_score helper with critical=-30/high=-15/medium=-7/low=-2 deductions, clamped 0–100, green/yellow/orange/red color bands), tenant-isolated aggregate stats (total_bundles, bundles_ready/processing/error, total_open_findings, findings_by_severity, most_recent_critical up to 5), dashboard router registered in main.py; HealthBar.tsx stacked proportional bar component (red/orange/yellow/blue/gray segments, "All Clear" green when zero), Dashboard.tsx page with 4 summary cards (Total Bundles/Open Criticals/Open Highs/Bundles with Issues), bundle health table (filename, status badge, health bar, score with color, open count, uploaded date, View button), most-recent-critical findings table (manager-only via isManager); dashboardApi.getStats() + BundleHealthSummary/DashboardStats interfaces in client.ts; /dashboard route added to App.tsx, / redirects to /dashboard, Dashboard + Bundles nav links added to Navbar; 8 new tests; 98 tests passing

## Phase 9 — Audit Trail & Finding Events
Goal: Full history of who did what to every finding
Deliverables: FindingEvent model, history timeline in UI
Success: Compliance-ready audit log; no mystery status changes
Planned: FindingEvent model (finding_id, user_id, event_type, old_value, new_value, note, created_at), auto-record on every PATCH /findings/:id and POST /findings/:id/explain, GET /findings/{id}/events, collapsible timeline in FindingCard

## Phase 10 — Notifications
Goal: Critical findings reach humans without polling the UI
Deliverables: Email + Slack alerts on critical/high findings
Success: On-call gets paged when a node goes NotReady
Planned: NotificationConfig model per tenant (email recipients, Slack webhook), Celery task after run_all_rules, SMTP email + Slack webhook delivery, dedup logic, GET/POST /api/v1/notifications/config (manager only), notification settings page in frontend

## Phase 11 — Comments & Discussion
Goal: Threaded conversation on findings instead of single notes field
Deliverables: Comment model, comment thread UI
Success: Analyst and manager can collaborate on a finding
Planned: Comment model (finding_id, user_id, body, created_at), GET/POST/DELETE /findings/{id}/comments, comment thread UI with real-time polling, reviewer_notes kept for backward compat

## Phase 12 — Bundle Comparison
Goal: Diff two bundles from the same cluster over time
Deliverables: Comparison view, new/resolved/persisting findings
Success: "What changed since last week?" answered in one click
Planned: GET /api/v1/bundles/compare?a={id}&b={id} (new/resolved/persisting findings + evidence diff), comparison logic matching by rule_id, side-by-side diff UI, optional cluster_name tag on upload for grouping history
