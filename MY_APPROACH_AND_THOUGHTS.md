# My Approach and Thoughts

## The Problem

Support bundle analysis is a signal-extraction problem. A bundle is a snapshot of a complex distributed system — thousands of lines of YAML, JSON, and logs that contain maybe a dozen actually relevant signals. The manual process is slow not because engineers are slow, but because finding the needle requires knowing what the needle looks like.

## What I Built

A web application that ingests Kubernetes support bundles and automatically surfaces findings, explains them in plain language, and generates ready-to-apply fixes.

**Detection layer** — 20 rules covering node health, pod lifecycle failures, storage issues, workload capacity, resource hygiene, KOTS configuration problems, and warning event patterns. Rules are deliberately deterministic: no LLM involved in detection, which means no hallucinations about what's actually in the bundle and no latency cost on every upload. Rules run in a Celery worker after parsing the bundle's YAML and JSON.

**Remediation layer** — Every finding includes a structured fix: plain-English explanation of what happened, why it matters, and how to fix it — plus ready-to-run kubectl commands and downloadable files (.sh script, .yaml patch, or .patch diff). KOTS configuration findings generate a minimal ConfigValues manifest that can be applied with `kubectl kots set config --config-file --merge --deploy` without touching any other config values.

**AI explanation layer** — Once findings are detected, Claude generates a plain-English explanation and specific remediation steps for each one. This is stored in the database so it is generated once per finding, not on every page load. The prompt enforces a structured format (explanation + `## Remediation Steps`) that the frontend renders as markdown.

**AI chat layer** — Each finding has a persistent chat thread. The system prompt is strictly scoped to the specific finding using hard boundaries — the model refuses any question not directly related to that finding and rejects prompt injection attempts. The boundary message is hardcoded so the model cannot be instructed to override it.

**Cross-bundle recurrence** — The dashboard surfaces findings that recur across multiple bundles, showing both a bundle count and total occurrence count per rule. A `pod_crashloop` firing across 8 of 10 customer bundles is a product bug; the same rule firing once is a customer misconfiguration. That distinction is surfaced directly in the UI.

**Role-based access** — Analysts can view findings, acknowledge them, comment, and download fixes. Managers and admins can resolve findings and delete bundles. The Resolve button is hidden from analysts entirely rather than shown disabled.

## Interesting Observations

The hardest part was the parsing, not the AI. Bundles are not perfectly consistent. A PodList can have items missing a `kind` field. Nodes report pressure conditions differently across versions. Writing rules robust to malformed or partial data required more defensive code than the detection logic itself.

The detection/explanation separation is a good architectural choice. Detection is fast, reliable, and testable with fixtures. Explanation quality can be improved by tweaking prompts without touching any detection logic.

The biggest limitation of the current approach is that findings are independent. OOM events, CrashLoop, and high restart count on the same pod are really one story told three ways. Grouping related findings into a single root-cause narrative would make the output significantly more useful and is the most interesting direction to explore next.
