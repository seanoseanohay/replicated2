# Friction: textAnalyze Analyzer Fails with "No matching files"

## Symptom
`textAnalyze` analyzer in a support bundle spec returns `detail: "No matching files"` with `severity: warn` even though the collector output file clearly exists in the generated bundle.

## Root Cause
The `textAnalyze` plugin resolves `fileName` using `collectorName` as a **path prefix**, but different collector types write files to **different directory structures** inside the support bundle. The plugin has one hardcoded rule (`<collectorName>/<fileName>`) that works for `runPod`/`exec` but is wrong for `http`, `logs`, and `data`.

### Where each collector type actually writes files

| Collector type | Actual path in bundle | What `textAnalyze` looks for when `collectorName` is set |
|---|---|---|
| `http` | `backend-health.json` (at bundle root) | `backend-health/backend-health.json` |
| `logs` | `<pod-name>/<container>.log` (at bundle root) | `backend-logs/<pod-name>/<container>.log` |
| `data` | `<collectorName>.log` (at bundle root) | `<collectorName>/<collectorName>.log` |
| `runPod` / `exec` | `<collectorName>/<namespace>/<pod>/<file>` | `<collectorName>/<namespace>/<pod>/<file>` (matches) |

## Evidence

- Extracted generated `support-bundle.tar.gz` and confirmed `backend-health.json` is at bundle root, not inside `backend-health/`.
- Removed `collectorName` from `textAnalyze` → analyzer resolved file correctly and matched regex.
- Known upstream bug: [troubleshoot PR #576](https://github.com/replicatedhq/troubleshoot/pull/576) and [PR #1865](https://github.com/replicatedhq/troubleshoot/pull/1865).

## Impact
- Any `textAnalyze` analyzer referencing `http`, `logs`, or `data` collector output with `collectorName` silently fails.
- Error message `"No matching files"` gives zero diagnostic info about *where* it searched.
- Users must manually extract bundles and inspect directory structure to discover the mismatch.

## Our Workaround

Use **root-relative `fileName`** and **omit `collectorName`** in `textAnalyze` when the collector is `http`, `logs`, or `data`:

```yaml
# Broken ("No matching files")
textAnalyze:
  collectorName: backend-health
  fileName: "backend-health.json"

# Works
http:
  collectorName: backend-health
  get:
    url: "http://backend:8000/health/ready"

textAnalyze:
  fileName: "backend-health.json"
  regex: '"status"\s*:\s*"ready"'
```

For `logs` collector output, the files are at `<pod-name>/<container>.log` at bundle root. Use a root-relative glob:

```yaml
textAnalyze:
  fileName: "bundle-analyzer-*/*.log"
  regex: 'error'
```

## Proposed Fix (Upstream)

1. **Short term**: Make `textAnalyze` path resolution **collector-type-aware**. When `collectorName` is present, resolve the search path based on the actual collector type instead of blindly prepending `<collectorName>/`.
2. **Better**: Add a new explicit `glob` or `searchPath` field to `textAnalyze` (and all analyzers) that accepts a bundle-root-relative pattern. Deprecate `collectorName` as a path modifier — it is a fake abstraction that conflates "reference a collector" with "modify the file path."
3. **Required**: Add diagnostic output showing the actual directories searched when returning `"No matching files"`. A debugging tool that fails silently is worse than useless.
4. **Required**: Publish a stable, versioned contract documenting exactly where each collector type writes its output inside the bundle.

## References

- `chart/templates/support-bundle.yaml` — current spec using root-relative `fileName` workaround
- [troubleshoot.sh docs — Collect All](https://troubleshoot.sh/docs/collect/all/)
- Upstream fix: [replicatedhq/troubleshoot#576](https://github.com/replicatedhq/troubleshoot/pull/576)
- Upstream fix: [replicatedhq/troubleshoot#1865](https://github.com/replicatedhq/troubleshoot/pull/1865)
