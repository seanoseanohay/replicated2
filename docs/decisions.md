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
