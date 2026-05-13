# Decision: Troubleshoot Specs Embedded as Kubernetes Secrets

**Status:** Accepted  
**Date:** 2026-05-13  
**Author:** OpenCode agent (via user guidance and empirical verification)  
**Scope:** `chart/templates/preflights.yaml`, `chart/templates/support-bundle.yaml`

---

## The Question

Should our Replicated Helm chart embed `troubleshoot.sh` preflight and support-bundle specs as:

1. **Raw CRDs** (`apiVersion: troubleshoot.sh/v1beta2`, `kind: Preflight` / `kind: SupportBundle`) — as shown in the canonical [`replicatedhq/troubleshoot`](https://github.com/replicatedhq/troubleshoot) examples?

2. **Kubernetes Secrets** (`apiVersion: v1`, `kind: Secret`, with `troubleshoot.sh/kind` labels) — as shown in the [Replicated Vendor documentation](https://docs.replicated.com/vendor/preflight-defining)?

This is a real point of contention because the two authoritative sources give contradictory-looking templates.

---

## What Is the Actual Difference?

These two patterns produce **entirely different Kubernetes resources** in the cluster.

### Pattern 1: Raw CRD (what the open-source examples show)

```yaml
apiVersion: troubleshoot.sh/v1beta2
kind: Preflight          <-- A CUSTOM resource type
metadata:
  name: my-preflights
spec:
  collectors: [...]
  analyzers: [...]
```

**What this means:**
- `kind: Preflight` is **not** a built-in Kubernetes type.
- The cluster's API server must have a **CustomResourceDefinition (CRD)** installed that teaches it what a `Preflight` is.
- Without that CRD, `kubectl apply` rejects it: `no matches for kind "Preflight"`.
- If the CRD *is* present, a controller (usually KOTS) can **watch** `Preflight` objects and run them automatically.

### Pattern 2: Secret Wrapper (what Replicated Helm docs require)

```yaml
apiVersion: v1
kind: Secret             <-- A STANDARD, built-in resource type
metadata:
  labels:
    troubleshoot.sh/kind: preflight   <-- Discovery label
  name: my-preflight-config
stringData:
  preflight.yaml: |      <-- The spec lives here as a STRING value
    apiVersion: troubleshoot.sh/v1beta2
    kind: Preflight
    spec:
      collectors: [...]
      analyzers: [...]
```

**What this means:**
- `kind: Secret` is a **standard** Kubernetes type. Every cluster understands it.
- No CRDs are required. This applies in **any** cluster.
- The `troubleshoot.sh/kind: preflight` label is a **convention** — the CLI plugin scans for Secrets with this label, reads the `stringData` key, parses the YAML string inside, and executes it.
- The actual troubleshoot spec is just **text inside the Secret**. The Kubernetes API server never sees it as a structured resource.

### The One-Sentence Difference

> **Raw CRD:** The cluster API server must know what a `Preflight` is (via CRD).  
> **Secret:** The cluster only needs to know what a `Secret` is. The Troubleshoot plugin reads the spec as text after the fact.

---

## Source A: The Open-Source `replicatedhq/troubleshoot` Examples

Repository: `https://github.com/replicatedhq/troubleshoot`

```yaml
# examples/preflight/all-analyzers-v1beta2.yaml
apiVersion: troubleshoot.sh/v1beta2
kind: Preflight
metadata:
  name: all-analyzers-v1beta2
spec:
  collectors: [...]
  analyzers: [...]
```

```yaml
# examples/support-bundle/sample-supportbundle.yaml
apiVersion: troubleshoot.sh/v1beta2
kind: SupportBundle
metadata:
  name: example
spec:
  collectors: [...]
  analyzers: [...]
```

These are the **canonical examples** for the open-source Troubleshoot engine. They use raw CRDs.

---

## Source B: The Replicated Vendor Documentation for Helm

URL: `https://docs.replicated.com/vendor/preflight-defining`

> "In your Helm chart `templates` directory, create a YAML file... In the YAML file, **add the following to create a Kubernetes Secret with the label `troubleshoot.sh/kind: preflight`**"

```yaml
# templates/preflight.yaml
apiVersion: v1
kind: Secret
metadata:
  # the troubleshoot.sh/kind: preflight label is required
  labels:
    troubleshoot.sh/kind: preflight
  name: "{{ .Release.Name }}-preflight-config"
stringData:
  # add a preflight.yaml key under stringData
  preflight.yaml: |
    apiVersion: troubleshoot.sh/v1beta2
    kind: Preflight
    metadata:
      name: preflights
    spec:
      collectors: []
      analyzers: []
```

URL: `https://docs.replicated.com/vendor/support-bundle-customizing`

> "In the YAML file, **add the following to create a Kubernetes Secret with the default support bundle spec**"

```yaml
# templates/support-bundle.yaml
apiVersion: v1
kind: Secret
metadata:
  # troubleshoot.sh/kind: support-bundle label is required
  labels:
    troubleshoot.sh/kind: support-bundle
  name: example
# add the spec in a support-bundle-spec key under stringData
stringData:
  support-bundle-spec: |
    apiVersion: troubleshoot.sh/v1beta2
    kind: SupportBundle
    metadata:
      name: support-bundle
    spec:
      collectors: []
      analyzers: []
```

These docs then show a **contrast section** for non-Helm:

> "For non-Helm applications or installations with KOTS v1.100.3 and earlier, add the **Preflight custom resource** to a YAML file at the root level of your release"

> "For non-Helm applications or installations with KOTS v1.94.1 and earlier, add the **SupportBundle custom resource** to a YAML file at the root level of your release"

**The documentation explicitly maps:**
- **Helm** → Secret
- **Non-Helm / KOTS ≤v1.100.3** → Raw CRD

---

## Empirical Test: Can Raw CRDs Be Applied to Our Cluster?

We tested applying raw `troubleshoot.sh/v1beta2` CRDs directly to our OrbStack k3s cluster:

```bash
$ cat > /tmp/raw-preflight.yaml << 'EOF'
apiVersion: troubleshoot.sh/v1beta2
kind: Preflight
metadata:
  name: test
spec:
  collectors: []
  analyzers: []
EOF
$ kubectl apply -f /tmp/raw-preflight.yaml
```

**Result:**
```
error: resource mapping not found for name: "test" namespace: "":
no matches for kind "Preflight" in version "troubleshoot.sh/v1beta2"
ensure CRDs are installed first
```

**Verification:**
```bash
$ kubectl get crd | grep troubleshoot
(no output)
```

**Conclusion:** Standard Kubernetes clusters do **not** have the `troubleshoot.sh/v1beta2` CRDs installed. Raw CRDs cannot be `kubectl apply`'d without first installing those CRDs.

---

## Why the Two Patterns Exist

| Pattern | Context | When CRDs Are Present | How Specs Are Consumed |
|---------|---------|----------------------|------------------------|
| **Raw CRD** | File-mode CLI usage | Not needed | `kubectl preflight ./file.yaml` reads the YAML directly; no cluster interaction required |
| **Raw CRD** | KOTS / in-cluster | **Installed by KOTS** | KOTS controller watches `Preflight`/`SupportBundle` CRDs in the cluster and runs them automatically |
| **Secret** | Replicated Helm | **Not needed** | CLI plugins discover specs by the `troubleshoot.sh/kind` label on standard `v1` Secrets |

The `replicatedhq/troubleshoot` examples are **generic** for the open-source engine. They work in two scenarios:
1. **File mode** — pass a local file path to the CLI plugin
2. **KOTS** — KOTS installs the CRDs and has a controller that processes them

**Our constraint: No KOTS.** We target **pure Helm installations** on arbitrary customer clusters where KOTS is not present and the `troubleshoot.sh/v1beta2` CRDs are **not installed**. A `v1/Secret` is the only universally applicable resource that applies in any cluster without prerequisites.

---

## Plugin Consumption Behavior

### `kubectl preflight` Plugin

From the plugin's own help text:

> "Unlike support-bundle, preflight does not support `--load-cluster-specs` because preflight checks are designed to run **before** an application is installed or upgraded. Since no deployment has occurred yet, there are **no in-cluster specs to discover**. Preflight specs must be provided via a URL, local file path, or stdin."

**Verified behaviors:**

| Invocation | Works? | Notes |
|------------|--------|-------|
| `kubectl preflight ./file.yaml` | ✅ | Reads local raw CRD file directly |
| `kubectl preflight - < file.yaml` | ✅ | Reads raw CRD from stdin |
| `helm template ... \| kubectl preflight -` | ✅ | Helm-rendered Secret content piped to stdin; plugin ignores the Secret wrapper and reads the raw spec inside |
| `kubectl preflight secret/ns/name/key` | ✅ | **Reads the raw spec from inside a Secret's `stringData` key** |
| `kubectl preflight -n mynamespace` | ❌ | No args = error: "requires at least 1 arg(s)" |

**Key insight:** `kubectl preflight` does **not** scan the cluster for Secrets by label. It requires an explicit file path, stdin, or `secret/namespace/name/key` argument. But it **can** read a spec from inside a Secret when given the explicit path.

### `kubectl support-bundle` Plugin

From the plugin's own help text:

> "If no arguments are provided, specs are **automatically loaded from the cluster by default**."
> "**Secret**: Load specs from a Kubernetes Secret. Format: `secret/namespace-name/secret-name[/data-key]`"

**Verified behaviors:**

| Invocation | Works? | Notes |
|------------|--------|-------|
| `kubectl support-bundle ./file.yaml` | ✅ | Reads local raw CRD file |
| `kubectl support-bundle - < file.yaml` | ✅ | Reads raw CRD from stdin |
| `kubectl support-bundle -n mynamespace` | ✅ | **Auto-discovers Secrets with `troubleshoot.sh/kind: support-bundle` label** |
| `kubectl support-bundle secret/ns/name/key` | ✅ | Explicit Secret path |
| `helm template ... \| kubectl support-bundle -` | ✅ | Reads rendered Secret from stdin |

**Key insight:** `kubectl support-bundle` **does** scan the cluster for Secrets by label when run without arguments. This is the primary customer support workflow — run `kubectl support-bundle -n <namespace>` and it auto-finds the app's spec.

---

## Helm Render Test: What Gets Templated

Our templates produce standard Kubernetes Secrets:

```yaml
# Rendered from templates/preflights.yaml
apiVersion: v1
kind: Secret
metadata:
  labels:
    troubleshoot.sh/kind: preflight
  name: "bundle-analyzer-preflight-config"
stringData:
  preflight.yaml: |
    apiVersion: troubleshoot.sh/v1beta2
    kind: Preflight
    ...
```

```yaml
# Rendered from templates/support-bundle.yaml
apiVersion: v1
kind: Secret
metadata:
  labels:
    troubleshoot.sh/kind: support-bundle
  name: "bundle-analyzer-support-bundle-config"
stringData:
  support-bundle-spec: |
    apiVersion: troubleshoot.sh/v1beta2
    kind: SupportBundle
    ...
```

These are **valid `v1` resources** that apply in any Kubernetes cluster, regardless of CRD presence.

---

## Alternative Considered: Raw CRD in Chart

**Why rejected:**

1. **CRDs not present:** `kubectl apply` fails with `no matches for kind "Preflight"` on standard clusters
2. **Helm CRD management complexity:** Helm has special `crds/` directory handling, but troubleshoot CRDs would need to be a chart dependency or manual pre-install step, adding friction
3. **Not required by Replicated:** The official Replicated Helm path does not mention CRD installation
4. **Secret works everywhere:** No prerequisites, no extra steps for customers

---

## References

| Source | URL | What It Says |
|--------|-----|-------------|
| Replicated Preflight Docs (Helm) | `https://docs.replicated.com/vendor/preflight-defining` | "create a Kubernetes Secret with the label `troubleshoot.sh/kind: preflight`" |
| Replicated Support Bundle Docs (Helm) | `https://docs.replicated.com/vendor/support-bundle-customizing` | "create a Kubernetes Secret with the default support bundle spec" |
| Replicated Docs (Non-Helm/KOTS) | Same pages, "non-Helm" sections | "add the **Preflight custom resource**" / "add the **SupportBundle custom resource**" |
| Troubleshoot Examples (Raw CRD) | `https://github.com/replicatedhq/troubleshoot` | Raw `troubleshoot.sh/v1beta2` CRDs — designed for file-mode or KOTS |
| `kubectl preflight --help` | Local output | "Preflight specs must be provided via a URL, local file path, or stdin" |
| `kubectl support-bundle --help` | Local output | "If no arguments are provided, specs are automatically loaded from the cluster" |

---

## Decision

**Use Kubernetes Secrets** (`v1/Secret` with `troubleshoot.sh/kind` labels) for both preflight and support-bundle specs in the Helm chart.

**Rationale:**
1. **No KOTS constraint:** We explicitly do not use KOTS. The chart must deploy on bare clusters where no `troubleshoot.sh` CRDs exist.
2. It is the **official Replicated documentation** for Helm-based applications
3. It **works in any cluster** without requiring CRD installation
4. It is **consumed by the CLI plugins** — preflight via explicit `secret/...` path or stdin, support-bundle via auto-discovery or explicit path
5. The raw CRD examples are for **different contexts** (file-mode CLI, KOTS) and would fail to deploy in our target environment

## Embedded Cluster v3 Consideration

**Does this change for EC v3?**

Embedded Cluster v3 includes KOTS in the management layer, and KOTS **does** install the `troubleshoot.sh/v1beta2` CRDs. So raw CRDs would likely apply successfully in an EC v3 cluster.

However, we keep the **Secret for all deployment targets** because:

1. **No KOTS is a hard constraint:** We explicitly do not target KOTS. The same Helm chart must work for **Helm-only** customers where KOTS is not present and CRDs are not installed. A raw CRD would fail `helm install` on these clusters.

2. **Official docs specify Secret for Helm universally:** The Replicated Helm docs make no exception for EC v3. They say "create a Kubernetes Secret" for all Helm chart templates.

3. **EC discovers specs from the release, not the live cluster:** The EC troubleshooting docs state that support bundles "**also include app-level details provided by any custom support bundle specs that you included in the application release**." This implies discovery happens during release packaging, where the Secret (in the chart templates) is scanned alongside the spec. The live-cluster CRD presence is irrelevant to release-level spec inclusion.

4. **Timing safety:** Even in EC v3, the order of operations is: EC installer → KOTS + CRDs → app Helm chart. If the chart contains raw CRDs, Helm might try to create them before KOTS has finished installing the CRD definitions, causing a race. A `v1/Secret` has no such dependency.

| Deployment Target | KOTS Present? | CRDs Present? | Raw CRD `helm install` | Secret `helm install` | Our Target? |
|-------------------|--------------|--------------|------------------------|----------------------|-------------|
| **Helm-only** | ❌ No | ❌ No | ❌ Fails | ✅ Works | ✅ **Yes** |
| **KOTS** | ✅ Yes | ✅ Yes | ✅ Works | ✅ Works | ❌ No |
| **Embedded Cluster v3** | ✅ Yes (embedded) | ✅ Yes | ✅ Likely works | ✅ Works | ✅ Yes, but chart must also work Helm-only |

**Conclusion for EC v3:** The Secret wrapper remains correct. Even though EC v3 has KOTS and CRDs, our chart must support the Helm-only path (no KOTS, no CRDs). The Secret is the only format that works in both contexts without branching.

---

## Future Reconsideration Trigger

- If Replicated changes their official Helm guidance to use raw CRDs with a mandatory CRD-installation prerequisite
- If the Troubleshoot project adds a Helm subchart that installs CRDs automatically
- If EC v3 provides a first-class mechanism to install CRDs before the app chart, AND Replicated updates the Helm docs to specify raw CRDs for EC deployments specifically
