# Friction Log

## 2026-05-13 — Troubleshoot Specs: Secret vs. Raw CRD Confusion

**Context:** Implementing Phase 3.1 (Preflights) and 3.2 (Support Bundles) for Replicated Helm chart.

**The Friction:**
Two authoritative sources gave contradictory templates for the same thing:

1. **Replicated Vendor Docs** (`docs.replicated.com`) say: *"create a Kubernetes Secret with the label `troubleshoot.sh/kind: preflight`"*
2. **Open-source Troubleshoot Examples** (`github.com/replicatedhq/troubleshoot`) show raw `troubleshoot.sh/v1beta2` CRDs (`kind: Preflight`, `kind: SupportBundle`)

Both are official. Both are correct. For different contexts. But nothing on either page explains *why* they differ or *when* to use which.

**What made it worse:**
- The open-source examples are the first thing you find when searching for "troubleshoot preflight example"
- The Replicated docs bury the Secret requirement in a code block without explaining the CRD prerequisite issue
- The contrast sections ("For non-Helm... use raw CRD") exist but are easy to miss
- No single page says: "Helm = Secret because arbitrary clusters don't have CRDs; KOTS/file-mode = raw CRD"

**What we had to discover empirically:**
```bash
$ kubectl apply -f raw-preflight.yaml
error: no matches for kind "Preflight" in version "troubleshoot.sh/v1beta2"
ensure CRDs are installed first
```

Standard clusters do NOT have the `troubleshoot.sh/v1beta2` CRDs. Raw CRDs fail to apply. This is not mentioned prominently in either set of docs.

**The Fix:**
- Use Secret wrapper per Replicated Helm docs
- Document the decision exhaustively in `docs/decision-troubleshoot-secret-vs-crd.md`
- Add inline comments to both template files explaining WHY it's a Secret

**Root Cause:** Replicated has two audiences — open-source troubleshoot users (file-mode, KOTS) and Helm vendors (deploy-anywhere) — but doesn't clearly signal which pattern belongs to which audience.

**Suggested Improvement for Replicated Docs:**
Add a single comparison table to both preflight and support-bundle docs:

| Your Setup | Use This | Why |
|---|---|---|
| Helm chart (Replicated) | `v1/Secret` + `troubleshoot.sh/kind` label | Works in any cluster; no CRDs required |
| KOTS / Embedded Cluster | Raw `troubleshoot.sh/v1beta2` CRD | KOTS installs CRDs automatically |
| File-mode / open-source | Raw `troubleshoot.sh/v1beta2` CRD | Passed directly to CLI plugin |

---

## 2026-05-13 — textAnalyze File Path Resolution

**Context:** Attempting to add automated log-scanning analyzers (textAnalyze) to the support bundle.

**The Friction:**
textAnalyze analyzers require a `fileName` pointing to collected log files inside the generated tar.gz. We tried:
- `fileName: "bundle-analyzer/bundle-analyzer-backend-*/backend.log"` — "No matching files"
- `fileName: "**/backend.log"` — "No matching files"
- `fileName: "cluster-resources/pods/logs/bundle-analyzer/bundle-analyzer-backend-*/backend.log"` — "No matching files"

All failed despite the files existing in the bundle.

**Root cause (likely):** The textAnalyze collector may not support glob patterns or nested paths inside the tar.gz, or the `collectorName` → file path mapping doesn't work the way we assumed. No error message indicates what path it was actually looking for.

**The Fix:**
Cut the textAnalyze analyzers entirely. They were trying to regex-scan logs for `error|exception|traceback` — but our app uses structured logging where those strings appear in benign contexts ("error handler initialized"). The signal-to-noise ratio was poor anyway.

**Replacement:** Added an `http` collector hitting the backend's `/health/ready` endpoint instead. This gives real functional signal (DB+Redis+S3 all accessible) with zero false positives.

**Lesson:** Don't fight plugin bugs for weak signal. Find a stronger signal that's easier to collect.

---

## [Add future friction entries below]
