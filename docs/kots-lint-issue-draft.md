# Draft GitHub Issue — DO NOT PUSH WITHOUT REVIEW

**Status: LOCAL DRAFT ONLY. Not pushed anywhere. Review and edit before pasting into github.com/replicatedhq/kots-lint/issues.**

Last revised: 2026-05-16 by Lawrence Keener.

---

## Suggested title

`helm-chart-missing` false positive on EC v3 releases using `ReplicatedImageRegistry` / `ReplicatedImageName` template functions

---

## Suggested labels

`bug`, `lint`, `embedded-cluster`, `air-gap`

---

## Issue body (copy below the line into the GitHub issue body field)

---

### Summary

The `helm-chart-missing` linter rule fires a false-positive error against every Embedded Cluster v3 release whose `helmchart.yaml` uses `ReplicatedImageRegistry` or `ReplicatedImageName` template functions in `spec.values`. This pattern is the **documented** way to support air-gap image rewriting for Helm-installed charts on EC v3 ([docs](https://docs.replicated.com/vendor/helm-packaging-airgap-bundles)). So every customer following the documented path hits this error.

The release itself is fully valid:
- Bundle builds in Vendor Portal
- Bundle downloads via the customer download URL
- Air-gap install completes end-to-end on a network-isolated VM
- All pods Run from the in-cluster registry (custom images) and containerd preload (infrastructure)

Only the Vendor Portal lint thinks something is wrong.

### Reproduction

A minimal EC v3 release that hits this:

**`embedded-cluster-config.yaml`**
```yaml
apiVersion: embeddedcluster.replicated.com/v1beta1
kind: Config
metadata:
  name: airgap-repro
spec:
  version: "3.0.0-beta.4+k8s-1.34"
```

**`helmchart.yaml`**
```yaml
apiVersion: kots.io/v1beta2
kind: HelmChart
metadata:
  name: my-app
spec:
  chart:
    name: my-app
    chartVersion: 0.1.0
    releaseName: my-app
  helmVersion: v3
  useHelmInstall: true
  values:
    backend:
      image:
        registry: '{{repl ReplicatedImageRegistry (HelmValue ".backend.image.registry") }}'
```

Plus any minimal Helm chart `my-app-0.1.0.tgz` with `Chart.yaml: name: my-app, version: 0.1.0` and an `image.registry` value in `values.yaml`.

Promote this to any channel. Vendor Portal shows on the release page:

```
Error: Could not find helm chart manifest for archive 'my-app-0.1.0.tgz'
Error helm-chart-missing
```

But the HelmChart CR exists, is well-formed, and has matching `spec.chart.name` and `spec.chart.chartVersion`.

### Root cause (traced in this repo)

In `pkg/kots/lint.go`, function `lintRenderContent`, the EC v3 ignored-function branch (~line 789 as of `main` at filing time):

```go
for _, file := range separatedSpecFiles {
    renderedContent, err := file.RenderContent(builder)
    if err == nil {
        file.Content = string(renderedContent)
        renderedFiles = append(renderedFiles, file)
        continue
    }
    if renderErr, ok := errors.Cause(err).(domain.RenderTemplateError); ok {
        if releaseIsECV3 && isECV3IgnoredFunctionError(renderErr.Error()) {
            continue   // ← file dropped from renderedFiles
        }
        // ... else fire "unable-to-render" error ...
    }
}
```

With the recognizer (same file):

```go
func isECV3IgnoredFunctionError(err string) bool {
    for _, fn := range []string{"ReplicatedImageName", "ReplicatedImageRegistry"} {
        if strings.Contains(err, fmt.Sprintf(`function "%s" not defined`, fn)) {
            return true
        }
    }
    return false
}
```

The intent is clearly to suppress the `unable-to-render` lint expression for functions that only exist at EC v3 runtime — that's correct. But the `continue` also skips `renderedFiles = append(renderedFiles, file)`, silently removing the HelmChart CR from the slice that downstream lints consume.

Downstream, `lintHelmCharts` runs `findAllKotsHelmCharts(renderedFiles)`. With the HelmChart CR missing from `renderedFiles`, `allHelmCharts` is empty. The final loop over `.tar.gz` files then fires `helm-chart-missing` for every chart archive because no matching HelmChart CR is found.

### Suggested fixes

**Option A (one-line)** — keep the file in `renderedFiles` unrendered:

```go
if releaseIsECV3 && isECV3IgnoredFunctionError(renderErr.Error()) {
    renderedFiles = append(renderedFiles, file)
    continue
}
```

Risk: other downstream lints that consume `renderedFiles` (`lintWithOPARendered`, `lintWithKubeval`) will see unrendered KOTS template strings (e.g., `'{{repl ReplicatedImageRegistry ... }}'`) as YAML scalar values. In practice these lints either skip non-stdlib resources (HelmChart is a kots.io/* CRD) or validate fields the templating doesn't touch, so the risk is small — but a contributor should verify against the lint test suite.

**Option B (slightly more surgical)** — pass original files to `lintHelmCharts` for fallback HelmChart CR discovery:

```go
// In Lint():
helmChartsLintExpressions, err := lintHelmCharts(renderedFiles, originalFiles, tarGzFiles)

// In lintHelmCharts:
allHelmCharts := findAllKotsHelmCharts(separatedRenderedFiles)
allHelmCharts = mergeUnique(allHelmCharts, findAllKotsHelmCharts(separatedOriginalFiles))
allHelmCharts = append(allHelmCharts, findAllECConfigHelmCharts(...)...)
```

This isolates the change to `lintHelmCharts` and doesn't perturb any other lint that consumes `renderedFiles`.

### Secondary observation — `LintConfig` doesn't seem to suppress this rule in Vendor Portal

We tried adding a `LintConfig` manifest to the release:

```yaml
apiVersion: kots.io/v1beta1
kind: LintConfig
metadata:
  name: bundle-analyzer-lint-config
spec:
  rules:
    - name: helm-chart-missing
      level: "off"
```

The file was included in the release (verified via `replicated release inspect`), syntactically matches the [LintConfig docs](https://docs.replicated.com/reference/custom-resource-lintconfig), but Vendor Portal still showed the `helm-chart-missing` error as `error` (not "off"). This suggests the Vendor Portal web-side lint may not honor LintConfig overrides, or may run a separate lint pipeline that ignores this customer-side configuration. May be the same root cause as the primary bug, may be a second issue worth investigating separately.

### Why this matters

`ReplicatedImageRegistry` is the documented Replicated-recommended way to support both online and air-gap installs with a single Helm chart on EC v3. Every Replicated customer who follows the published guidance hits this error on every release. The error reads as a hard error in Vendor Portal (red banner, "1 error found"), undermines customer trust in the build, and creates a long tail of confused support questions.

The release itself works correctly — we have reproductions on a network-isolated VM showing all pods Running from the in-cluster registry. The fix is one or two lines. The cost of leaving it is every air-gap-shipping vendor going through the same debugging cycle.

### Additional context

We hit this on `replicated` CLI version (current latest) and Vendor Portal as of 2026-05-16. EC bundle version `3.0.0-beta.4+k8s-1.34`. Released chart sequences 48 through 59 all reproduced; releases 47, 51, and 57 (without the `values:` block) lint clean but produce non-air-gap-capable installs.

Detailed bootcamp notes and full reproduction logs available in our internal friction log: [link to internal doc if/when you decide to share].
