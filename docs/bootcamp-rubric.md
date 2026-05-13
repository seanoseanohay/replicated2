# Bootcamp Rubric — Full Map

**Source:** `/Users/lawrenceleekeener/Downloads/bootcamp_rubric.pdf`  
**App:** Bundle Analyzer  
**Target:** Helm + Embedded Cluster v3 (no KOTS)

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ COMPLETE | Done, verified, documented |
| 🔄 IN PROGRESS | Partially done, needs more work |
| ⏳ PENDING | Not started |
| ⚠️ BLOCKED | Waiting on external dependency |
| 📝 NOTE | Special consideration |

---

## Tier 0: Build It

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 0.1 | Build custom web app with stateful component | Show app running locally; custom Dockerfile; real backend + persistent storage | ✅ COMPLETE | FastAPI + React, PostgreSQL, Redis, MinIO |
| 0.2 | Helm chart packages and deploys app | Open app in browser; `helm lint` clean; `values.schema.json` | ✅ COMPLETE | `chart/`, `values.schema.json` |
| 0.3 | 2+ Helm subcharts (1 stateful, embedded + BYO) | Show conditional subchart; install with embedded stateful; set Helm value for BYO external | ✅ COMPLETE | `postgresql.enabled` toggle, `externalPostgresql` values |
| 0.4 | Kubernetes best practices | Liveness/readiness probes; resource requests/limits; delete pod → data persists; dedicated `/health` endpoint | ✅ COMPLETE | `/health/live`, `/health/ready` in backend; probes in all deployments |
| 0.5 | HTTPS with certificate options | Open app at `https://`; valid TLS cert shown in browser | ✅ COMPLETE | cert-manager, manual upload, self-signed with `lookup` + `helm.sh/resource-policy: keep` |
| 0.6 | App waits for database | No crashloops on startup; init container or app logic checks DB before starting | ✅ COMPLETE | Init containers in backend/worker/beat wait for PostgreSQL + Redis + MinIO |
| 0.7 | 2+ user-facing demoable features | Demo end-to-end in production app | ✅ COMPLETE | Bundle upload + parse + AI explain + findings workflow; dashboard + comparison |

---

## Tier 1: Automate It

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 1.1 | Images built and pushed to private registry | CI run log showing build + push; images in private registry | ✅ COMPLETE | GitHub Actions builds + pushes to GHCR |
| 1.2 | Scoped Replicated RBAC policy | Custom policy assigned to Service Account | 📝 NOTE | Using default Replicated CI token; custom RBAC not explicitly configured but may be covered by GitHub Actions secret |
| 1.2 (alt) | PR workflow with `.replicated` file | Passing Actions run triggered by PR; creates release + tests it | ✅ COMPLETE | `.github/workflows/replicated.yml` — creates release on PR |
| 1.3 | Release workflow (merge to main → Unstable) | Passing Actions run triggered by merge to main | ✅ COMPLETE | `.github/workflows/replicated.yml` — promotes to Unstable on merge |
| 1.4 | Email notifications on Stable promotion | Receive email at `@replicated.com` when promoted to Stable | ⏳ PENDING | Need to configure email notifications for Stable channel |

---

## Tier 2: Ship It with Helm

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 2.1 | Replicated SDK as subchart, renamed | `kubectl get deployment <app>-sdk` shows pod Running | ✅ COMPLETE | SDK named `bundle-analyzer-sdk` in `Chart.yaml` dependencies |
| 2.2 | All images proxied through custom domain | `kubectl get pods` shows every image starts with custom domain | ✅ COMPLETE | `images.bundlyzer.com` configured in Vendor Portal; all images rewritten |
| 2.4 | Custom metrics visible in Vendor Portal | At least 1 meaningful app metric on Instance Details page | ✅ COMPLETE | `metrics_reporter.py` sends bundle counts, findings by severity, user totals |
| 2.5 | License entitlement gates real feature | Custom license field; app reads from SDK at runtime; feature toggles without redeploy | ✅ COMPLETE | `ai_chat_enabled` field gates AI explanations; middleware enforces |
| 2.6 | Update available banner | Banner appears when update available; respects license state | ✅ COMPLETE | `UpdateBanner.tsx`, `update_service.py` checks SDK `/app/info` and `/app/updates` |
| 2.6 (part 2) | License validity enforced | App blocks/warns when license expired or invalid | ✅ COMPLETE | `LicenseWall.tsx`, `license_check_middleware`, `is_license_valid()` parses `expires_at` |
| 2.7 | Optional ingress (off by default) | Ingress optional; when enabled, routes traffic to app | ✅ COMPLETE | `ingress.enabled: false` default; verified with `helm template` |
| 2.8 | Service type configurable | `helm template --set` renders ClusterIP, NodePort, LoadBalancer | ✅ COMPLETE | `frontend.service.type` and `backend.service.type` parameterized |
| 2.9 | Instance live, named, tagged, showing metrics | Instance reports healthy, custom metrics visible | ✅ COMPLETE | Instance `a81dbf1` named "bundle-analyzer-prod", tagged "environment:production" |
| 2.10 | Services show as healthy in instance reporting | All services report `ready` in SDK app/status | ✅ COMPLETE | 18 resources all `ready` via `/api/v1/app/status` |

---

## Tier 3: Support It

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 3.1 | Preflight checks (5 required) | Run twice: once failing, once passing; clear actionable messages | ✅ COMPLETE | `chart/templates/preflights.yaml` — 6 checks; verified passing + failing scenarios |
| 3.2 | Log collection covers all components | Separate logs collector per component; maxLines/maxAge limits; all log dirs non-empty | ✅ COMPLETE | 8 collectors, all with `limits:`; verified all 8 components non-empty |
| 3.3 | Health endpoint checked with http collector + textAnalyze | http collector hits `/health` endpoint; textAnalyze parses response for pass/fail | ✅ COMPLETE | http collector → `/health/ready`; analyzer checks `statusCode == 200` / `error` / `!= 200` |
| 3.4 | Status analyzers for all workload types | deploymentStatus, statefulsetStatus, jobStatus, replicasetStatus as applicable | ✅ COMPLETE | 4× deploymentStatus + 3× statefulsetStatus (no jobs or replicasets in app) |
| 3.5 | textAnalyze catches known app failure pattern | textAnalyze with regex on log file; analyzer fires on pattern; clear remediation message | ✅ COMPLETE | textAnalyze searches `bundle-analyzer-*/*.log` with regex matching 6 known backend error patterns (Failed to process bundle, bundle_upload_s3_error, etc.); verified no false positives in healthy state; regex proven via synthetic `data` collector test |
| 3.6 | Storage class and node readiness verified | storageClass analyzer fails when no default SC; nodeResources fails when node not Ready | ✅ COMPLETE | `nodeResources` checks CPU+memory; `storageClass` conditional on explicit config |
| 3.7 | Support bundle generated from app UI + uploaded to Vendor Portal | "Generate Support Bundle" button in UI; uploads to Vendor Portal; visible on Instance Details | ⏳ PENDING | Need to add UI button + SDK upload endpoint integration |

---

## Tier 4: Ship It on a VM (Embedded Cluster v3)

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 4.1 | App installs on bare VM with EC v3 | Fresh VM → EC install → `sudo k0s kubectl get pods -A` all Running → app in browser | ⏳ PENDING | Need CMX VM or local VM; EC Config manifest needed in release |
| 4.2 | In-place upgrade without data loss | Release 1 → create data → upgrade to release 2 → data still present, all pods Running | ⏳ PENDING | Requires EC v3 install first |
| 4.3 | Air-gapped install | Build air gap bundle → transfer to VM → install with bundle only → all pods Running | ⏳ PENDING | Requires air gap bundle build in Vendor Portal |
| 4.6 | App icon and name set correctly | Screenshot showing correct icon + app name in installer | ⏳ PENDING | Need to set in Application CR or Vendor Portal |
| 4.7 | License entitlement gates configurable feature (EC path) | License field controls feature; config screen item hidden/locked when disabled | ⏳ PENDING | Requires KOTS Admin Console config screen (Tier 5 overlap) |

---

## Tier 5: Config Screen (KOTS / Admin Console)

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 5.0 | External stateful component toggle with conditional fields | Install with embedded (show pod) and BYO (show no pod, external instance); config screen reveals/hides connection fields | 📝 NOTE | Not doing KOTS. For EC v3, this is handled via Helm values, not KOTS Config screen. May need to adapt or skip. |
| 5.1 | Configurable app feature wired through config screen | Enable/disable feature via config screen; show working/gone in app | 📝 NOTE | Same as above — KOTS-specific. For pure Helm, features are toggled via `values.yaml`. |
| 5.2 | Generated default value survives upgrade | Auto-generated value (e.g., DB password) persists across upgrade without reconfiguring | 📝 NOTE | We use PostgreSQL subchart which generates passwords via Secret; Helm `lookup` preserves them. But this is KOTS Config screen behavior. |
| 5.3 | Input validation | Config item with regex validation; blocks/accepts based on format | 📝 NOTE | KOTS Config screen feature. For Helm, validation is in `values.schema.json`. |
| 5.4 | Help text on all config items | `help_text` present on every config item | 📝 NOTE | KOTS-specific. Our `values.yaml` has comments but no structured help_text. |

**📝 Tier 5 Decision:** We are NOT doing KOTS. Tier 5 tasks are KOTS Admin Console config screen features. For Embedded Cluster v3 + Helm path, equivalent functionality is handled via Helm `values.yaml` and `values.schema.json`. We may need to document how our Helm values map to these requirements, or accept that Tier 5 is partially not applicable to our deployment model.

---

## Tier 6: Deliver It (Enterprise Portal v2)

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 6.1 | Enterprise portal branding | Screenshot: custom logo, favicon, title, primary/secondary colors | ⏳ PENDING | Configure in Vendor Portal → Enterprise Portal settings |
| 6.2 | Enterprise portal custom email sender | Invitation email arrives from custom domain, not Replicated address | ⏳ PENDING | Need custom domain with deliverability configured |
| 6.3 | Enterprise portal security center | Log in as customer, visit Security Center, see vulnerabilities | ⏳ PENDING | May need securebuild image to reduce CVEs |
| 6.4 | Enterprise portal custom setup instructions | GitHub repo integrated; customize left nav + content for install/operating instructions | ⏳ PENDING | Create docs repo, integrate GitHub app |
| 6.5 | Helm Chart reference in EPv2 docs | Automated helm chart reference in `toc.yaml`; at least 1 field not documented elsewhere | ⏳ PENDING | Generate from `values.schema.json` |
| 6.6 | Terraform modules in EPv2 docs | Generated terraform modules, enabled/disabled by license field | 📝 NOTE | "Does not need to work. Simple claude-generated fake module sufficient." |
| 6.8 | Enterprise portal self-serve sign-up | Share sign-up URL; complete flow; customer record appears in Vendor Portal | ⏳ PENDING | Enable self-service signups |
| 6.9 | End-to-end install via Enterprise Portal | As customer, follow install instructions → running app; once for Helm, once for EC | ⏳ PENDING | Requires Enterprise Portal fully configured |
| 6.10 | Upgrade instructions work without downtime | Test upgrade via Enterprise Portal for both Helm and EC | ⏳ PENDING | |

---

## Tier 7: Operationalize It

| # | Task | Acceptance Criteria | Status | Notes / Files |
|---|------|---------------------|--------|---------------|
| 7.1 | Notifications (email + webhook) | Show email and webhook notifications triggered on account activity | ✅ COMPLETE | `NotificationConfig` model, SMTP + Slack webhooks; notifications on critical/high findings |
| 7.2 | Explain security posture | Speak to CVEs in application and how to reduce them | ⏳ PENDING | Run `trivy` or similar; document findings |
| 7.3 | Sign your images | Images signed with cosign or similar | ⏳ PENDING | Add image signing to CI pipeline |
| 7.4 | Network policy option in CMX | Run app, exercise all functionality, deliver network policy report showing 0 outbound | ⏳ PENDING | Use CMX network policy feature; requires CMX VM |

---

## Summary by Tier

| Tier | Name | Tasks | Complete | In Progress | Pending | Notes |
|------|------|-------|----------|-------------|---------|-------|
| 0 | Build It | 7 | 7 | 0 | 0 | |
| 1 | Automate It | 4 | 3 | 0 | 1 | 1.4 (Stable email) pending |
| 2 | Ship It with Helm | 10 | 10 | 0 | 0 | |
| 3 | Support It | 7 | 6 | 0 | 1 | 3.7 (UI bundle upload) pending |
| 4 | Ship It on a VM | 5 | 0 | 0 | 5 | All require EC v3 install |
| 5 | Config Screen | 5 | 0 | 0 | 5 | KOTS-specific; may adapt for Helm |
| 6 | Deliver It | 9 | 0 | 0 | 9 | Enterprise Portal v2 |
| 7 | Operationalize It | 4 | 1 | 0 | 3 | 7.1 notifications done |

**Total Complete: 27 / 51 tasks (53%)**

---

## Next Priority Tasks

1. **3.7** — Support bundle generated from app UI + uploaded to Vendor Portal
2. **1.4** — Email notifications on Stable promotion
3. **4.1** — EC v3 install on bare VM (requires CMX credits or local VM)
4. **4.3** — Air-gapped install (requires air gap bundle build)
5. **6.1–6.4** — Enterprise Portal setup (branding, custom domain, docs)
6. **7.2–7.4** — Security, signing, network policy

---

## Key Decisions / Friction Logged

- **Secret vs. Raw CRD for troubleshoot specs:** Documented extensively in `docs/decision-troubleshoot-secret-vs-crd.md` and `docs/friction-log.md`
- **No KOTS:** We target Helm + Embedded Cluster v3 only. KOTS Admin Console features (Tier 5) need adaptation or may be skipped.
- **EC v3, not v2:** All embedded cluster tasks use EC v3 per rubric.
- **Custom domain:** `images.bundlyzer.com` configured for proxy registry.
