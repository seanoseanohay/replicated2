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

## Phase 9 — Audit Trail & Finding Events ✓ COMPLETE
Goal: Full history of who did what to every finding
Deliverables: FindingEvent model, history timeline in UI
Success: Compliance-ready audit log; no mystery status changes
Built: FindingEvent model (finding_id, user_id, actor, event_type, old_value, new_value, note, created_at) with composite index on (finding_id, created_at), alembic migration 0004, FindingEventRead schema, auto-record status_changed/note_added events on PATCH /findings/:id, ai_explained event on POST /findings/:id/explain, created event in Celery task after bulk insert, GET /api/v1/bundles/{bundle_id}/findings/{finding_id}/events endpoint with tenant check; collapsible "History" section in FindingCard with colored dot timeline (blue/gray/purple/green), relative timestamps, actor+description display, cached in component state; eventsApi.getEvents() + FindingEvent interface in client.ts; 4 tests passing

## Phase 10 — Notifications ✓ COMPLETE
Goal: Critical findings reach humans without polling the UI
Deliverables: Email + Slack alerts on critical/high findings
Success: On-call gets paged when a node goes NotReady
Built: NotificationConfig model (tenant_id unique, email_enabled, email_recipients, slack_enabled, slack_webhook_url, notify_on_severities, created_at, updated_at), alembic migration 0005, NotificationConfigRead/Update schemas, SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM/APP_BASE_URL config settings, notifications service (send_email_notification skips if SMTP_HOST empty, send_slack_notification with rich Slack message, notify_bundle_findings filters by severity+status), Celery task calls notify_bundle_findings after run_all_rules wrapped in try/except, GET+POST /api/v1/notifications/config (require_manager), notifications router registered in main.py; NotificationSettings.tsx page with email/slack toggles and recipients/webhook/severities inputs (manager-only guard), /settings/notifications route in App.tsx, Settings link in Navbar (manager-only); notificationApi.getConfig()/updateConfig() + NotificationConfig interface in client.ts; 5 tests passing

## Phase 11 — Comments & Discussion ✓ COMPLETE
Goal: Threaded conversation on findings instead of single notes field
Deliverables: Comment model, comment thread UI
Success: Analyst and manager can collaborate on a finding
Built: Comment model (finding_id+bundle_id FKs with CASCADE, actor, user_id nullable, body Text, created_at, updated_at), alembic migration 0006, CommentRead/CommentCreate schemas (body 1–4096 chars validator), GET/POST/DELETE /api/v1/bundles/{bundle_id}/findings/{finding_id}/comments with tenant check + own-comment-or-manager delete authorization, comments router registered in main.py; Comments section in FindingCard with chat-style thread (actor bold + body + relative timestamp + delete button for own/manager), textarea+submit for new comments, lazy load with state cache; commentApi.list/create/delete() + Comment interface in client.ts; 6 tests passing

## Phase 12 — Bundle Comparison ✓ COMPLETE
Goal: Diff two bundles from the same cluster over time
Deliverables: Comparison view, new/resolved/persisting findings
Success: "What changed since last week?" answered in one click
Built: FindingSummary/ComparisonResult schemas, GET /api/v1/bundles/compare?bundle_a={id}&bundle_b={id} endpoint (placed before /{bundle_id} route to avoid UUID parse conflict) with tenant validation on both bundles, rule_id set diff for new/resolved/persisting, sorted output; BundleCompare.tsx page (/bundles/compare) with two dropdowns for bundle selection, Compare button, 3-column results grid (red/New, green/Resolved, yellow/Persisting) with severity badges, summary counts bar; Compare link in Navbar; comparisonApi.compare() + ComparisonResult/FindingSummary interfaces in client.ts; 5 tests passing

## Phase 2.4 — Replicated Custom Metrics Reporting ✓ COMPLETE
Goal: Report real app activity to Replicated Vendor Portal
Deliverables: metrics_reporter service, APScheduler heartbeat, event-driven emission, manual endpoint
Success: Vendor Portal Instance Details shows bundle counts, findings, and user totals
Built: _send_metrics() via PATCH to Replicated SDK in-cluster API, collect_and_send_metrics_sync() with synchronous DB session querying bundles by status, open findings by severity, and total users; hourly APScheduler job added in backend lifespan (metrics_scheduler_started), event-driven calls after finding status change, bundle deletion, and user registration; POST /api/v1/metrics/report manager-only endpoint; METRICS_ENABLED toggle (default true, false for local dev); removed custom-metrics from Celery beat schedule because workers lack SDK sidecar; verified with mock SDK in kind cluster — payload contains real scalar values only (no nested objects)

## Phase 2.5 — Replicated TLS Configuration ✓ COMPLETE
Goal: Secure HTTPS ingress with multiple certificate options
Deliverables: Self-signed cert persistence, cert-manager support, manual upload path
Success: No cert regeneration on helm upgrade; HTTPS redirect works
Built: tls-secret.yaml using Helm `lookup` function and `helm.sh/resource-policy: keep` to preserve existing self-signed certificates across upgrades; `regenerateSelfSignedCert` toggle to force rotation; `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` annotation for automatic HTTP→HTTPS redirect; `docs/tls-setup.md` documenting three modes (auto-provisioned cert-manager, manually uploaded secret, self-signed for testing)

## Phase 2.6 — Replicated Update Available Banner ✓ COMPLETE
Goal: Surface pending app updates to end users inside the UI
Deliverables: Update status endpoint, in-memory cache, dismissible banner
Success: Users see a blue banner when a newer release is available; yellow banner when license is invalid
Built: `update_service.py` fetches Replicated SDK `/api/v1/app/info` (current version + license validity) and `/api/v1/app/updates` (available releases) with 5-minute in-memory TTL cache; version comparison by `versionLabel` (available when next != current); `GET /api/v1/updates/status` returns `UpdateStatusRead` (`available`, `version`, `notes`, `license_valid`, `current_version`) with `require_auth` dependency; `UpdateBanner.tsx` mounts inside `ProtectedLayout`, shows blue info banner for available updates, yellow warning banner for invalid license, dismissible via localStorage key per version; 8 backend tests covering no-update, new-version, invalid-license, SDK-unreachable, empty updates list, multiple-updates picks newest, and auth-required

## Phase 2.7 — Optional Ingress ✓ COMPLETE
Goal: Make the Ingress resource optional and off by default so the chart deploys on clusters without an ingress controller
Deliverables: Conditional Ingress template, off-by-default toggle
Success: `helm template` with defaults renders no Ingress; with `ingress.enabled=true` renders a working Ingress routing to the frontend service
Built: `chart/templates/ingress.yaml` wrapped in `{{- if .Values.ingress.enabled }}`; `chart/values.yaml` sets `ingress.enabled: false` by default; Ingress routes `/.Values.ingress.hosts[].paths[]` to `bundle-analyzer-frontend` service on port 3000; supports TLS via cert-manager, manually uploaded secrets, or self-signed certificates (via `tls-secret.yaml` lookup + `helm.sh/resource-policy: keep`); `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` annotation for HTTP→HTTPS redirect; end-to-end verified with `helm template` (no Ingress with defaults, Ingress present when enabled) and deployed cluster returning HTTP 200 via ingress IP

## Phase 2.8 — Service Type Configurable ✓ COMPLETE
Goal: Allow the frontend service type to be configured so the app is reachable even without an ingress controller
Deliverables: Parameterized service type in frontend and backend service templates
Success: `helm template --set frontend.service.type=NodePort` renders NodePort; `=LoadBalancer` renders LoadBalancer; default remains ClusterIP for use with Ingress
Built: `chart/templates/frontend-service.yaml` uses `{{ .Values.frontend.service.type }}`; `chart/templates/backend-service.yaml` uses `{{ .Values.backend.service.type }}`; `chart/values.yaml` defaults both to `ClusterIP`; all three types verified with `helm template`: default=ClusterIP, NodePort=NodePort, LoadBalancer=LoadBalancer; frontend service targets pod port 3000, backend targets 8000

## Phase 2.9 — Instance Live, Named, Tagged ✓ COMPLETE
Goal: Instance reports as healthy in Vendor Portal, shows custom metrics, and is identifiable
Deliverables: Live instance with custom metrics visible, friendly name, and tags
Success: Vendor Portal Instance Details page shows Ready status, 100% uptime, custom metrics with real app data, named "bundle-analyzer-prod", tagged "environment:production"
Built: Instance `a81dbf1` running in cluster with all 18 resources reporting "ready"; custom metrics sent via `PATCH /api/v1/app/custom-metrics` showing bundles_ingested=2, open findings by severity, total_users=4; instance named "bundle-analyzer-prod" and tagged "environment:production" via Vendor Portal UI

## Phase 2.10 — Services Healthy in Instance Reporting ✓ COMPLETE
Goal: All app services show up as healthy in Replicated instance reporting
Deliverables: SDK app/status endpoint returning all workloads as ready
Success: SDK /api/v1/app/status returns 18 resources (deployments, statefulsets, services, PVCs) all with state "ready"
Built: Replicated SDK auto-discovers and watches all K8s resources in the release namespace; backend, frontend, worker, beat deployments all "ready"; postgresql, redis, minio statefulsets all "ready"; all services and PVCs "ready"; app status shows "Ready" with 100% uptime in Vendor Portal

## Phase 3.1 — Preflight Checks ✓ COMPLETE
Goal: Validate deployment prerequisites before installation to prevent failed installs
Deliverables: troubleshoot.sh preflight spec with required checks, embedded in Helm chart as Secret
Success: Preflights run via kubectl preflight plugin; show passing and failing scenarios with clear, actionable messages
Built: chart/templates/preflights.yaml — Kubernetes Secret with troubleshoot.sh/kind: preflight label containing preflight.yaml spec aligned with official Replicated troubleshoot.sh examples; checks: (1) clusterVersion requires K8s >= 1.25.0, (2) nodeResources requires >= 4Gi memory and >= 2 CPU cores, (3) distribution fails on docker-desktop and microk8s with links to supported options, (4) postgres connectivity only when externalPostgresql configured (conditional via Helm template), (5) textAnalyze on HTTP collector checks Anthropic API reachability, (6) storageClass check only when explicit storageClass is configured (conditional via Helm template) to avoid false failures on clusters using default StorageClass; all failure messages explain what went wrong and how to fix it; verified with kubectl preflight plugin on passing scenario (embedded PostgreSQL, 2 pass + 2 warn = overall PASS) and failing scenario (bad external DB host, DB connectivity FAIL with hostname resolution error = overall FAIL)

## Phase 3.2 — Support Bundle Log Collection ✓ COMPLETE
Goal: Capture logs from every app component for offline troubleshooting, plus runtime health analyzers
Deliverables: troubleshoot.sh support bundle spec with logs collectors and runtime health analyzers, embedded in Helm chart as Secret
Success: `kubectl support-bundle` generates a tar.gz containing non-empty logs for all 8 components and 10 passing analyzer results
Built: chart/templates/support-bundle.yaml — Kubernetes Secret with troubleshoot.sh/kind: support-bundle label containing support-bundle-spec aligned with official Replicated troubleshoot.sh examples; 8 dedicated logs collectors targeting each component by label selector with `limits:` block (maxLines: 10000, maxAge: 720h, maxBytes: 5000000) matching official sample-supportbundle.yaml structure; `clusterInfo` and `clusterResources` collectors scoped to release namespace for privacy; `http` collector to backend `/health/ready` endpoint testing DB+Redis+S3 connectivity; runtime health analyzers: clusterVersion, nodeResources, deploymentStatus (backend/worker/frontend/beat), statefulsetStatus (postgresql/redis/minio), http (backend health endpoint); verified with `kubectl support-bundle` plugin — generated archive contains non-empty logs for all 8 components (backend 2.3MB, frontend 335KB, sdk 202KB, worker 29KB, postgresql 9KB, beat 9KB, redis 1.4KB, minio 504B) and all 10 analyzers report pass including backend health showing `{"status":"ready","checks":{"database":"ok","redis":"ok","storage":"ok"}}`

**Proof of Acceptance Criteria (2026-05-13):**
Run `kubectl support-bundle -n bundle-analyzer --interactive=false`. Output: archive generated, all 10 analyzers pass. Extracted log file listing confirms all 8 major components have non-empty log directories:
```
  2392072  cluster-resources/pods/logs/.../backend.log          ← app (backend)
     9284  cluster-resources/pods/logs/.../beat.log             ← app (beat)
   336166  cluster-resources/pods/logs/.../frontend.log       ← app (frontend)
    29739  cluster-resources/pods/logs/.../worker.log         ← app (worker)
   202522  cluster-resources/pods/logs/.../replicated.log     ← operator (sdk)
      504  cluster-resources/pods/logs/.../minio.log          ← stateful service
     9049  cluster-resources/pods/logs/.../postgresql.log     ← stateful service
     1447  cluster-resources/pods/logs/.../redis.log          ← stateful service
```
Each collector sets `maxLines: 10000`, `maxAge: 720h`, and `maxBytes: 5000000` per official examples.
