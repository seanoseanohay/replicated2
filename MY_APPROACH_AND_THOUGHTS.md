# My Approach and Thoughts

## The Problem

Support bundle analysis is fundamentally a signal-extraction problem. A bundle is a snapshot of a complex distributed system at a moment in time — thousands of lines of YAML, JSON, and logs that contain maybe a dozen actually relevant signals. The manual process is slow not because engineers are slow, but because finding the needle requires knowing what the needle looks like.

## What I Built

A web application that ingests Troubleshoot support bundles and automatically surfaces findings, explains them in plain language, and lets engineers interact with the results.

**Detection layer** — 19 rules covering node health, pod lifecycle failures, storage issues, workload capacity, resource hygiene, and warning event patterns. Rules are deliberately deterministic: no LLM involved in detection, which means no hallucinations about what's actually in the bundle and no latency cost on every upload. The rules run synchronously in a Celery worker after parsing.

**AI explanation layer** — Once findings are detected, Claude (Haiku) generates a plain-English explanation and specific remediation steps for each one. This is stored in the database so it's only generated once per finding. The prompt enforces a structured format (explanation + `## Remediation Steps`) that the frontend renders as markdown.

**AI chat layer** — Each finding has a persistent chat thread. The system prompt is strictly scoped to the specific finding — the model can only answer questions about that finding and refuses anything outside that boundary. This prevents the chat from becoming a general-purpose assistant while still being genuinely useful for follow-up questions.

**Cross-bundle recurrence** — The dashboard surfaces findings that appear across multiple bundles. A `pod_crashloop` firing in 8 of 10 customer bundles is a product bug; the same rule firing once is a customer misconfiguration. That distinction matters.

## Interesting Observations

The hardest part wasn't the AI — it was the parsing. Bundles aren't perfectly consistent. A PodList can have items that lack a `kind` field. Nodes report pressure conditions differently across versions. Writing rules that are robust to malformed or partial data required more defensive code than I expected.

The detection/explanation separation turned out to be a good architectural choice. Detection is fast, reliable, and testable with fixtures. Explanation quality can be improved independently by tweaking prompts without touching the detection logic.

The biggest open question is **semantic clustering** — grouping findings that aren't the same rule but describe the same underlying problem (e.g., OOM events, CrashLoop, and high restart count on the same pod are really one story). That would require embeddings or a more sophisticated AI analysis pass and is the most interesting direction to explore next.
