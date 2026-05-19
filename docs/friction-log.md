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

**Root cause (confirmed):** Official troubleshoot project PRs prove this is a known bug. `textAnalyze` constructs search paths using only `collectorName + fileName`, missing intermediate namespace/pod directories for `exec`/`runPod` collectors, and failing entirely on `http` collector output files. The fix was merged in PR #1865 (Sep 2025) into the v1beta3 branch — our plugin v0.128.1 predates it.

References:
- PR #576 — "Fix run collector text analyze file path mismatch" (May 2022): https://github.com/replicatedhq/troubleshoot/pull/576
- PR #1865 — "Fix/exec textanalyze path clean" (Sep 2025): https://github.com/replicatedhq/troubleshoot/pull/1865

**The Fix:**
Cut the textAnalyze analyzers entirely. They were trying to regex-scan logs for `error|exception|traceback` — but our app uses structured logging where those strings appear in benign contexts ("error handler initialized"). The signal-to-noise ratio was poor anyway.

**Replacement:** Added an `http` collector hitting the backend's `/health/ready` endpoint instead. This gives real functional signal (DB+Redis+S3 all accessible) with zero false positives.

**Lesson:** Don't fight plugin bugs for weak signal. Find a stronger signal that's easier to collect.

---

## 2026-05-13 — Support Bundle Proof Run

**Context:** Final verification that Phase 3.2 acceptance criteria are met.

**The Criteria:**
> "Show the support bundle spec has a separate logs collector for each major component (app, stateful service, any operator). Each collector sets maxLines or maxAge limits. Run the bundle and show each component's log directory is present and non-empty in the output."

**What We Did:**
```bash
$ kubectl support-bundle -n bundle-analyzer --interactive=false
{
    "analyzerResults": [ /* 10 analyzers all pass */ ],
    "archivePath": "support-bundle-2026-05-13T14_30_16.tar.gz"
}
```

Then extracted and verified every log file:
```bash
$ tar -tzf support-bundle-*.tar.gz | grep cluster-resources/pods/logs
# Listed 8 log files, all non-empty
```

**Results:**
- 4 app components: backend (2.3MB), worker (29KB), beat (9KB), frontend (335KB) ✅
- 1 operator: sdk/replicated (202KB) ✅
- 3 stateful services: postgresql (9KB), redis (1.4KB), minio (504B) ✅

**Lesson:** Automated analyzers (textAnalyze) failed for us, but the core requirement — *collect logs, show they're there* — is straightforward to verify. Don't over-engineer the analyzers; make sure the collectors work.

---

## 2026-05-14 — Vendor Portal "Missing" app-info and license Files in Helm-Only Bundles

**Context:** Uploading support bundles via SDK to Vendor Portal (Phase 3.7 final verification). Bundle was generated from a Helm-only app (no KOTS Admin Console).

**The Friction:**
After successfully uploading bundles, the Vendor Portal analysis showed two persistent warnings:
- `warn : No app-info file found`
- `warn : No license file found`

The bundle clearly contained `app-info.json` and `license.yaml` at the root level, both present and valid. Yet the built-in analyzers still warned.

**What we tried (empirical discovery):**

1. **Flat bundle:** Files at `./app-info.json` and `./license.yaml` → insights count: 0 (no analyzers ran)
2. **Standard root dir:** `support-bundle-*/app-info.json` + `support-bundle-*/license.yaml` → warnings still present
3. **KOTS path + wrong format:** `kots/admin_console/app-info.json` with camelCase `InstanceID` + raw YAML license → "No instance ID found" + "No license ID found"
4. **KOTS path + correct format:** `kots/admin_console/app-info.json` with snake_case `instance_id` + KOTS License CRD (`apiVersion: kots.io/v1beta1`, `kind: License`, `metadata.name`, `spec.*`) → **0 warnings**

**Root cause:**
The Vendor Portal's built-in analyzers are hardcoded with KOTS assumptions:
1. **Path:** They search `kots/admin_console/app-info.json` and `kots/admin_console/license.yaml`, not the bundle root
2. **App-info format:** Expects snake_case `instance_id` matching the KOTS `ReportingInfo` Go struct
3. **License format:** Expects a full KOTS License CRD, not a flat YAML dump of the SDK `/license/info` response

This is entirely undocumented for Helm-only apps. The docs assume KOTS/EC context where KOTS Admin Console generates these files automatically.

**The Fix:**
Post-process the bundle before upload to create both:
1. Root-level files for human inspection (raw SDK body as JSON + flat YAML)
2. KOTS-compat files under `kots/admin_console/` with the exact paths and formats the Vendor Portal expects

**Lesson:** When the Vendor Portal has built-in analyzers that expect KOTS-specific file layouts, a Helm-only app must provide KOTS-compat shim files even though KOTS is not part of the architecture.

---

## 2026-05-14 — EC v3 Install: Chart Bloat from Missing .helmignore

**Context:** Creating release 30 for EC v3 testing. The chart tarball was 1.3GB (sequence 30) vs 210KB (sequence 31).

**The Friction:**
Helm `helm package` includes every file in the chart directory by default. Old artifacts accumulated:
- `bundle-analyzer-0.1.0.tgz` (210KB stale chart)
- `bundle-analyzer-0.1.1.tgz` (1.3GB because it recursively included itself + embedded-cluster/ dir)
- `embedded-cluster/config.yaml` (20 bytes — an old EC config that shouldn't ship with the chart)
- `.DS_Store` (macOS metadata)

This caused Helm install to fail with:
```
Error: create: failed to create: Secret "sh.helm.release.v1.bundle-analyzer.v1" is invalid: data: Too long: may not be more than 1048576 bytes
```

**The Fix:**
Created `chart/.helmignore`:
```
.DS_Store
*.tgz
.git
.gitignore
embedded-cluster/
```

Rebuilt chart → 210KB. Release 31 created successfully.

**Lesson:** Always add `.helmignore` to Helm charts. Without it, packaging is non-deterministic and accumulates artifacts.

---

## 2026-05-14 — EC v3 Install: Multi-Arch Image Builds Required

**Context:** Deploying release 31 to an x86_64 CMX VM. Pods showed `ImagePullBackOff`.

**The Friction:**
The error was NOT auth-related (we had already fixed that). It was:
```
no match for platform in manifest: not found
```

The images were built with `docker build --platform linux/arm64` on an M1 Mac. The VM was `x86_64`. Containerd couldn't find an amd64 layer in the manifest.

**The Fix:**
Rebuilt all app images with `docker buildx build --platform linux/amd64,linux/arm64`:
- `replicated2-backend:latest`
- `replicated2-frontend:latest`
- `replicated2-worker:latest`
- `replicated2-beat:latest` (this one was missing entirely — beat is a separate deployment but shared the same Docker build)

**Lesson:** When target deployment environment is unknown (CMX VMs, customer clusters), always build multi-arch images. Single-arch builds are fine for local dev only.

---

## 2026-05-14 — EC v3 Install: Image Pull Auth Domain Mismatch

**Context:** Pods in the EC v3 cluster couldn't pull images from `images.bundlyzer.com`.

**The Friction:**
KOTS created `enterprise-pull-secret` with auth for:
- `proxy.replicated.com`
- `registry.replicated.com`

But the Helm chart rendered image URLs pointing to:
- `images.bundlyzer.com/proxy/bundle-analyzer/ghcr.io/...`

Containerd only sends credentials for the exact domain. `images.bundlyzer.com` → 401 Unauthorized.

**What we tried:**
1. Generic EC binary from GitHub — fails because it doesn't embed the app release
2. Patching the deployment image URLs to `proxy.replicated.com` — would work but doesn't fix the root cause
3. Patching the `enterprise-pull-secret` to add `images.bundlyzer.com` with the same auth token — **this worked**

**Root cause:** The proxy registry token is NOT domain-scoped. A valid token for `proxy.replicated.com` is also valid for `images.bundlyzer.com`. The issue is purely that the secret didn't list the domain.

**The Fix:**
Patched `enterprise-pull-secret` to add `images.bundlyzer.com` entry copying the `proxy.replicated.com` auth credentials.

**Proper Fix (for chart):** The Helm chart should probably use `proxy.replicated.com` directly for EC contexts, or Replicated should ensure custom proxy domains are pre-populated in the pull secret.

**Lesson:** Custom proxy domains (`images.bundlyzer.com`) require explicit entries in image pull secrets, even if they resolve to the same registry backend.

---

## 2026-05-14 — EC v3 Install: SDK License Secret Name + Config Format

**Context:** SDK subchart pod (`bundle-analyzer-sdk`) was stuck in `ContainerCreating` then `CrashLoopBackOff`.

**Two separate issues:**

### Issue A: Secret name mismatch
- Chart expected volume from secret `bundle-analyzer-license`
- The secret existed but was named differently in the Helm values
- Created `bundle-analyzer-license` secret manually from `license.yaml`

### Issue B: Config file vs directory mount
- SDK expects `/etc/replicated/config.yaml` as a **file**
- Secret mount without `subPath` creates a **directory** called `config.yaml`
- SDK container crashed with: `read /etc/replicated/config.yaml: is a directory`

**The Fix:**
1. Created secret: `kubectl create secret generic bundle-analyzer-license --from-file=license=license.yaml`
2. Patched deployment to add `subPath: license` on the volumeMount

### Issue C: SDK bootstrap needs license ID env var
Even after fixing the mount, SDK logged:
```
failed to bootstrap: failed to get replicated and app ids: failed to get replicated deployment uid: failed to get replicated deployment: the server could not find the requested resource
```

Patched deployment to add env var `REPLICATED_INTEGRATION_LICENSE_ID=3DaG0n3OEZsofvqExNHccIptaKO`. SDK started but still shows bootstrap errors in logs. App itself is Ready regardless.

**Lesson:** SDK subchart in EC v3 has fragile initialization that depends on exact secret naming, file mounts (not directories), and environment variables. The main app runs fine without SDK being fully healthy.

---

## 2026-05-14 — EC v3 Install: Vendor Portal Required for Installer URL

**Context:** Need the EC v3 installer bundle URL to install on a bare VM.

**The Friction:**
The Replicated CLI (`replicated channel inspect`, `replicated customer inspect`) only shows:
- KOTS install instructions (`kubectl kots install`)
- kURL/EC v2 install instructions (`curl | sudo bash` to `k8s.kurl.sh`)

There is **no CLI command** that exposes the EC v3 installer download URL.

**What we tried:**
1. `replicated customer inspect` — shows Helm CLI instructions only
2. `replicated channel inspect --output json` — no EC v3 URL field
3. `replicated api get` — no `/embedded/` or `/installer/` endpoint for EC v3
4. Direct URL construction (`ec-k8s.replicated.com`, `get.replicated.com`, `tf-embedded-cluster-binaries.s3...`) — all 401/404
5. Generic EC binary from GitHub releases — fails because it has no embedded app release

**The actual URL format** (only available from Vendor Portal web UI):
```
curl -f "https://replicated.app/embedded/bundle-analyzer/ec-test" -H "Authorization: <installation_id>" -o bundle-analyzer-ec-test.tgz
```

**The Fix:**
Had to ask the user to open the Vendor Portal web UI and copy the install instructions.

**Lesson:** EC v3 is CLI-incomplete. The installer URL is web-UI-only. Automation/scripting of EC v3 installs requires either:
- Vendor Portal API access (undocumented), or
- Manual copy-paste of the install command

---

## 2026-05-14 — EC v3 Install: Release Promotion Version Flag Behavior

**Context:** Promoting release 30 to the Unstable channel.

**The Friction:**
```bash
replicated release promote 30 Unstable --version "0.1.1-ec"
# → reports success
# → channel ls still shows release 28
```

Multiple retries, with and without `--version`, all reported success but the channel never updated.

**What worked:**
Creating a NEW channel (`EC-Test`) and promoting to it worked on the first try. Release 30 showed up immediately.

**Hypothesis:** The Unstable channel had `semverRequired: true` and release 30 had a `versionLabel` that didn't match semver expectations, or there was a validation error silently swallowing the promotion. The EC-Test channel was created fresh with no constraints.

**Lesson:** If release promotion reports success but the channel doesn't update, try:
1. `channel inspect <id>` to verify (not just `channel ls`)
2. Create a fresh channel with no constraints as a test
3. Check if the version label violates channel semver rules

---

## 2026-05-14 — EC v3 Upgrade: Helm SSA Conflicts from Manual Patches

**Context:** In-place upgrade from 0.1.1-ec-fixed to 0.1.2 on an EC v3 cluster (Phase 4.2).

**The Friction:**
Helm upgrade failed with Server-Side Apply (SSA) conflicts:
```
UPGRADE FAILED: conflict occurred while applying object kotsadm/enterprise-pull-secret:
  Apply failed with 1 conflict: conflict with "kubectl-client-side-apply" using v1: .data..dockerconfigjson
&& conflict occurred while applying object kotsadm/bundle-analyzer-sdk:
  Apply failed with 1 conflict: conflict with "kubectl-patch" using apps/v1:
  .spec.template.spec.containers[name="replicated"].volumeMounts[mountPath="/etc/replicated/config.yaml"].subPath
```

**Root cause:** In Phase 4.1, we used `kubectl patch` to fix two live-cluster issues:
1. Added `images.bundlyzer.com` auth entry to `enterprise-pull-secret`
2. Added `subPath: license` to the SDK deployment's config volume mount

These patches created SSA field ownership claims under `kubectl-client-side-apply` and `kubectl-patch`. When KOTS ran `helm upgrade` for the new release, Helm (as field manager `helm`) could not take ownership of those fields because other managers already owned them.

**Impact:**
- Helm returned exit code 1
- Admin Console shows version 0.1.2 as "failed" in version history
- BUT: the changed deployment spec (frontend image tag `latest` → `0.1.2`) was still applied by Kubernetes
- The new frontend pod rolled out successfully
- The app remained Ready and functional
- No data was lost

**The Fix:**
For future releases, reconcile ALL manual patches back into the Helm chart before creating a new release. Emergency `kubectl patch` is for debugging only — it creates upgrade debt.

Specific fixes needed:
1. `enterprise-pull-secret`: Either disable `bundle-analyzer-sdk.createPullSecret` and manage the secret in chart templates, or create a secondary secret for custom proxy domains
2. SDK `subPath`: The Replicated SDK subchart (v1.19.4) does not expose `subPath` customization for the license volume mount. Either:
   - Create a separate ConfigMap/Secret with the license as a single file and use `extraVolumes`/`extraVolumeMounts`
   - Or accept that SDK bootstrap may fail in EC v3 Helm-only mode (app works regardless)

**Lesson:** `kubectl patch` is a debugging tool, not a configuration management tool. Any live patch that survives more than one release cycle will cause SSA conflicts on upgrade. Always patch the chart, never the cluster.

---

## 2026-05-14 — EC Version Confusion: Deployed v2.17.1 Instead of v3

**Context:** Phase 4.1 bootcamp task requires "Embedded Cluster v3". I told the user we were using v3, but `embedded-cluster-config.yaml` specified `version: "2.17.1+k8s-1.34"` — which is EC v2.

**The Friction:**
When asked "are we using EC v3?" I confidently said yes. I was wrong. The config format `2.17.1+k8s-1.34` is the production/stable EC v2 format. EC v3 uses semver like `3.0.0-beta.4`.

This matters because:
1. **Different installer binaries** — v2 and v3 have different CLI commands and flags
2. **Different cluster architectures** — v3 may use different k0s versions, storage providers, or network configs
3. **Different upgrade paths** — v2 uses KOTS-managed upgrades; v3 uses a different mechanism
4. **Different config schemas** — `embeddedcluster.replicated.com/v1beta1` may behave differently between v2 and v3

**How this happened:**
I saw "Embedded Cluster" in the bootcamp rubric and assumed "EC = v3" without verifying the actual version string format. EC v2.17.1 is the current production version, so the config was valid — just not the version the task asked for.

**The Fix:**
Update `embedded-cluster-config.yaml`:
```yaml
spec:
  version: "3.0.0-beta.4"  # or current v3 version
```

Then tear down the v2 cluster and rebuild with v3.

**Lesson:** Always verify the actual version string against the documentation. Don't assume a product name implies a specific version. EC v2 and v3 are different products with different behaviors.

---

## 2026-05-14 — EC v3: Version String Format Blocks Air Gap Build

**Context:** Creating release 39 with `version: "3.0.0-beta.4"` in `embedded-cluster-config.yaml`. Air gap build failed with "1 error found" and `curl` to installer endpoint returned `{"error":"An online bundle is not available for version 0.1.8-v3"}`.

**The Friction:**
EC v3 version strings must include the Kubernetes version suffix in the format `+k8s-1.34`. Without it, the Replicated platform cannot build the embedded cluster bundle.

The docs say:
> "Embedded Cluster appends the version of Kubernetes to the version label in the format `+k8s-1.34`. For example, Embedded Cluster `3.0.0-alpha-26+k8s-1.34` uses Embedded Cluster `3.0.0-alpha-26` and Kubernetes 1.34."

But the example at the top of the same page shows:
```yaml
version: "3.0.0-beta.1"
```

Without the `+k8s-1.34` suffix. This is contradictory — the prose says it's appended, the example omits it. In practice, omitting it causes the air gap/embedded bundle build to fail silently.

**The Fix:**
```yaml
spec:
  version: "3.0.0-beta.4+k8s-1.34"  # MUST include +k8s-X.YY suffix
```

**Lesson:** The `+k8s-1.34` suffix is required, not optional. Always include it even when docs examples omit it.

---

## 2026-05-14 — EC v3 Headless Install Requires Config CR

**Context:** Running `sudo ./bundle-analyzer install --license license.yaml --headless --yes` on EC v3.

**The Friction:**
The installer fails immediately with:
```
failed to submit config values: HTTP 400 - load config item values: find Config resource: no kots.io/v1beta1 Config resource found
```

Even for a Helm-only app with no KOTS config items, EC v3 headless mode requires a `kots.io/v1beta1 Config` custom resource to exist in the release. Without it, the installer cannot proceed.

**The Fix:**
Add a minimal Config CR to the release manifests:
```yaml
apiVersion: kots.io/v1beta1
kind: Config
metadata:
  name: bundle-analyzer-config
spec:
  groups:
    - name: general
      title: General
      items:
        - name: hostname
          title: Hostname
          type: text
          default: "bundle-analyzer.local"
```

**Lesson:** EC v3 headless install requires a Config CR even if the app has no configuration items. The UI-based install path may skip this, but headless mode validates it strictly.

---

## 2026-05-14 — EC v3 Generated Pull Secret Missing Custom Proxy Domain

**Context:** App pods in EC v3 cluster failing with `ErrImagePull` / `401 Unauthorized` from `images.bundlyzer.com`.

**The Friction:**
Replicated automatically creates an `enterprise-pull-secret` in the app namespace with auth for:
- `proxy.replicated.com`
- `registry.replicated.com`

But our chart uses `images.bundlyzer.com` (custom proxy domain configured in Vendor Portal). The generated secret does NOT include auth for custom proxy domains. Pods using ServiceAccounts without explicit `imagePullSecrets` cannot pull images.

**The Fix:**
1. Patch the secret to add the custom domain:
```bash
kubectl patch secret enterprise-pull-secret -n bundle-analyzer --type merge -p '{"data":{".dockerconfigjson":"<base64-of-updated-config>"}}'
```

2. Patch all app ServiceAccounts to use the secret:
```bash
kubectl patch sa bundle-analyzer-backend -n bundle-analyzer -p '{"imagePullSecrets":[{"name":"enterprise-pull-secret"}]}'
```

**Lesson:** Custom proxy registry domains require manual secret patching in EC v3. The platform generates auth for standard domains only. For a proper fix, the chart should create its own pull secret or the Replicated platform should include all configured proxy domains.

---

## 2026-05-14 — EC v3 SDK License Secret Needs Dual Key Names

**Context:** SDK pod in EC v3 failing to start after fixing image pull issues.

**The Friction:**
The SDK subchart v1.19.4 expects the license secret to have:
1. A key named `config.yaml` — mounted as a file via `subPath: config.yaml` (NOT `license` or any other name)
2. A key named `integration-license-id` — used as an env var via `valueFrom: secretKeyRef`

Creating a secret with only `license` (the intuitive name from the license file) causes the volume mount to create a directory instead of a file, and the SDK crashes with `read /etc/replicated/config.yaml: is a directory`.

**The Fix:**
Create the secret with BOTH keys:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bundle-analyzer-license
stringData:
  config.yaml: |  # Must be exactly this key name for volume mount
    apiVersion: kots.io/v1beta1
    kind: License
    ...
  integration-license-id: "3DaG0n3OEZsofvqExNHccIptaKO"  # Must be exactly this key name for env var
```

**Lesson:** The SDK subchart has rigid secret key naming requirements. The `config.yaml` key name is hardcoded in the `subPath` mount spec. Always verify the subchart template expectations, not just the values.yaml documentation.

---

## [Add future friction entries below]
