# Decisions

## Backend Framework
Decision: FastAPI
Reason: Lightweight, async support
Tradeoffs: Less opinionated

## Architecture Style
Decision: Pipeline
Reason: Matches processing stages
Tradeoffs: Complexity in orchestration

## Detection Strategy
Decision: Hybrid (rules + AI)
Reason: Rules run deterministically on every bundle for baseline coverage; AI layer adds explanations and remediations on demand
Tradeoffs: AI adds latency and cost; gated behind AI_ENABLED flag so system works fully offline without it

## AI Integration
Decision: Anthropic Claude via official SDK; AI_ENABLED=false by default
Reason: Air-gapped deployments must function without AI; opt-in model avoids surprise API costs
Tradeoffs: Engineers must configure key and flip flag to unlock AI features

## Findings Model
Decision: Findings stored in PostgreSQL with status workflow (open/acknowledged/resolved)
Reason: Persistent audit trail; supports async review workflow across multiple engineers
Tradeoffs: Requires migration management as rules evolve

## Rate Limiting
Decision: slowapi (per-IP, per-endpoint)
Reason: Protect upload and AI endpoints from abuse without requiring auth infrastructure
Tradeoffs: IP-based limiting is bypassable behind NAT; can upgrade to tenant-key-based later

## Container Security
Decision: Non-root appuser in Docker, resource limits on worker
Reason: Defense-in-depth; worker processes untrusted bundle content
Tradeoffs: Slight complexity in Dockerfile; file permission care needed for volume mounts

## Deployment
Decision: Hosted + Offline
Reason: Enterprise requirements
Tradeoffs: Increased maintenance

## Replicated Custom Metrics
Decision: Event-driven + heartbeat hybrid, backend-only SDK calls
Reason: Replicated SDK sidecar only runs in the backend pod; workers and beat lack it. Heartbeat ensures Vendor Portal always has recent data even when no user activity occurs.
Tradeoffs: APScheduler adds a lightweight thread; metrics are best-effort (fire-and-forget) to avoid blocking API requests

## TLS Certificate Persistence
Decision: Helm `lookup` + `helm.sh/resource-policy: keep` for self-signed certs
Reason: Prevents certificate regeneration on every `helm upgrade`, avoiding browser cache warnings and Ingress TLS disruption
Tradeoffs: Slightly more complex template; explicit `regenerateSelfSignedCert=true` required to force rotation

## Troubleshoot Spec Embedding (Preflights & Support Bundles)
Decision: Kubernetes Secret wrapper (`v1/Secret` with `troubleshoot.sh/kind` labels) instead of raw `troubleshoot.sh/v1beta2` CRDs
Reason: Raw CRDs require the `troubleshoot.sh/v1beta2` CRDs to be installed in the cluster, which is not true for arbitrary customer clusters. A `v1/Secret` applies everywhere. The `troubleshoot.sh/kind` label enables CLI plugin discovery. This matches the official Replicated Helm documentation (which mandates Secrets) rather than the open-source troubleshoot examples (which are for file-mode or KOTS).
Tradeoffs: Adds a layer of indirection; spec is nested under `stringData` keys; preflight plugin cannot auto-scan by label (must use explicit `secret/ns/name/key` or stdin). See `docs/decision-troubleshoot-secret-vs-crd.md` for exhaustive analysis, test outputs, plugin behavior matrices, and the raw CRD failure logs.
