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

## Phase 3.1 — Extended Detection (Warnings & Capacity) ✓ COMPLETE
Goal: Catch degraded-but-not-down cluster states
Deliverables: 5 new detection rules, updated registry, new tests
Success: Warning-level issues surface before they become critical
Built: node_pressure (DiskPressure/MemoryPressure/PIDPressure node conditions, medium), deployment_unavailable (availableReplicas < desiredReplicas, medium), statefulset_unavailable (readyReplicas < replicas, medium), hpa_maxed (HPA at maxReplicas cannot scale further, medium), warning_event_reasons (dangerous Warning event reasons grouped by reason with high/medium severity, threshold=3); registry updated with all 5 rules; 9 new tests added

## Phase 7 — Authentication & Roles
Goal: Real user identity, not just X-Tenant-ID header
Deliverables: Login, JWT tokens, role-based access control
Success: Users log in, managers see more than analysts
Planned:
- User model (id, email, hashed_password, role, tenant_id, created_at)
- Alembic migration 0003
- POST /api/v1/auth/register (invite-only or open, configurable)
- POST /api/v1/auth/login → returns JWT access + refresh tokens
- POST /api/v1/auth/refresh
- JWT middleware replacing X-Tenant-ID header (tenant derived from token)
- Role enum: analyst | manager | admin
- Route guards: analysts cannot resolve findings or delete bundles
- Frontend: login page, token storage, auth context, protected routes
- Future: OAuth (Google/GitHub) plug-in point

## Phase 8 — Dashboard & Health Overview
Goal: At-a-glance cluster health across all bundles
Deliverables: Global dashboard, per-bundle health bar, aggregate stats
Success: Green means go, red means wake someone up
Planned:
- GET /api/v1/dashboard — aggregate stats across all bundles for tenant
  { total_bundles, bundles_by_status, findings_by_severity, most_recent_critical }
- Per-bundle health score: weighted severity formula → 0-100 → color band
  (100=all green, <60=yellow, <30=orange, 0=red)
- Dashboard page: summary cards (total bundles, open criticals, open highs)
- Health bar component: stacked color bar (critical/high/medium/low/info) per bundle
- Bundle list enhanced: health bar visible on each row
- Manager view: cross-bundle findings table (all open criticals across all clusters)

## Phase 9 — Audit Trail & Finding Events
Goal: Full history of who did what to every finding
Deliverables: FindingEvent model, history timeline in UI
Success: Compliance-ready audit log, no mystery status changes
Planned:
- FindingEvent model (finding_id, user_id, event_type, old_value, new_value, note, created_at)
- event_type enum: status_changed | note_added | ai_explained | created
- Auto-record event on every PATCH /findings/:id and POST /findings/:id/explain
- GET /api/v1/bundles/{id}/findings/{id}/events
- Frontend: collapsible timeline on each FindingCard showing history
- Integrates with Phase 7 auth (user_id populated from JWT)

## Phase 10 — Notifications
Goal: Critical findings reach humans without them polling the UI
Deliverables: Email + Slack alerts on critical/high findings
Success: On-call gets paged when node goes NotReady
Planned:
- NotificationConfig model per tenant (email recipients, Slack webhook URL)
- Celery task triggered after run_all_rules: send_notifications(bundle_id, findings)
- Email via SMTP (configurable): critical/high findings summary
- Slack webhook: rich message with severity color, finding title, bundle link
- Dedup logic: don't re-notify for same rule_id on same bundle
- GET/POST /api/v1/notifications/config — manager only (Phase 7 role guard)
- Frontend: notification settings page (manager role)

## Phase 11 — Comments & Discussion
Goal: Threaded conversation on findings instead of single notes field
Deliverables: Comment model, comment thread UI
Success: Analyst and manager can collaborate on a finding
Planned:
- Comment model (finding_id, user_id, body, created_at, updated_at)
- GET /api/v1/bundles/{id}/findings/{id}/comments
- POST /api/v1/bundles/{id}/findings/{id}/comments
- DELETE /api/v1/.../comments/{id} (own comment or manager)
- Frontend: comment thread below finding details, real-time via polling
- reviewer_notes field deprecated in favor of comments (kept for backward compat)

## Phase 12 — Bundle Comparison
Goal: Diff two bundles from the same cluster over time
Deliverables: Comparison view, new/resolved/persisting findings
Success: "What changed since last week?" answered in one click
Planned:
- GET /api/v1/bundles/compare?a={id}&b={id}
  Returns: new_findings, resolved_findings, persisting_findings, evidence_diff summary
- Comparison logic: match findings by rule_id across two bundles
- Frontend: side-by-side or diff-style view
- Bundle tagging: optional cluster_name tag on upload for grouping history
