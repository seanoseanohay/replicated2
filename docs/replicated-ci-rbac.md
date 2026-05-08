# Replicated CI RBAC Policy

This document describes the scoped RBAC policy required for the CI service account that runs the Replicated PR and release workflows.

## Goal

Create a custom, reduced-scope RBAC policy in the Replicated Vendor Portal and assign it to the CI service account token stored in `REPLICATED_API_TOKEN`.

## Why Scoped RBAC?

The CI token should have the minimum permissions needed to create releases and run tests. It must **not** have permissions to manage team members, billing, customers, or app settings.

## Steps in the Vendor Portal

1. Log in to the [Replicated Vendor Portal](https://vendor.replicated.com).
2. Navigate to **Team & Permissions**.
3. Enable the **Custom RBAC Policies** feature if it is not already on.
4. Create a **new custom policy** named `CI Service Account`.
5. Use the resource permissions below.
6. Create a **Service Account** and assign it this policy.
7. Copy the service account token and store it as `REPLICATED_API_TOKEN` in the GitHub repository secrets.
8. Ensure the service account is granted access to the app with slug `awesome-sauce`.

## Recommended Policy Permissions

| Resource | Permission | Reason |
|----------|-----------|--------|
| `kots/app/[]/read` | **Allow** | Read app metadata and list apps |
| `kots/app/[]/release/read` | **Allow** | List existing releases |
| `kots/app/[]/release/write` | **Allow** | Create new releases from `.replicated` |
| `kots/app/[]/channel/read` | **Allow** | List channels (e.g., Unstable) |
| `kots/app/[]/channel/write` | **Allow** | Create temporary channels if needed |
| `kots/app/[]/channel/[]/promote` | **Allow** | Promote releases to channels |

## Explicitly Denied (do not include)

| Resource | Permission | Reason |
|----------|-----------|--------|
| `kots/app/[]/team/*` | **Deny** | Prevent CI from managing team members |
| `kots/app/[]/settings/*` | **Deny** | Prevent CI from changing app settings |
| `kots/app/[]/customer/*` | **Deny** | Prevent CI from managing customers |
| `kots/app/[]/billing/*` | **Deny** | Prevent CI from accessing billing |

## Troubleshooting

If the workflow fails with `App not found: awesome-sauce` and `replicated app ls` returns an empty list, the service account token is authenticated but does not have access to the app. Verify:

1. The app slug in `.replicated` matches the app in the Vendor Portal.
2. The service account is assigned to the app.
3. The policy attached to the service account includes `kots/app/[]/read`.

### App name vs. app slug mismatch

The Replicated CLI `--app` flag expects the **app slug**, not the **app name**. In the Vendor Portal these can differ:

- **Name:** `awesome_sauce`
- **Slug:** `awesome-sauce`

**What we tried first:** Updating `.replicated` to use the slug (`appSlug: awesome-sauce`) alone did **not** resolve the `App not found` error. The workflow continued to fail.

**What actually fixed it:** Renaming the app in the Vendor Portal so the **name matches the slug exactly** (e.g., changing the name from `awesome_sauce` to `awesome-sauce`). Once the name and slug were identical, the CLI accepted the reference and the workflow succeeded.

**Takeaway:** When creating an app in the Vendor Portal, ensure the app **name and slug are identical** from the start. This avoids ambiguity in both the CLI and the `.replicated` configuration. If they already differ, rename the app to match the slug rather than trying to work around the mismatch in `.replicated`.

**How to verify:** Run `replicated app ls` in the workflow (or locally with the same token). The `SLUG` column is the value the CLI expects. The `NAME` column is not accepted by `--app`.

## Learnings / Friction Points

This section captures real issues encountered while wiring the CI token and policy, so future readers don't repeat the same debugging cycle.

### 1. Missing `app/read` permission

**Symptom:** `replicated app ls` returns an empty table, and every subsequent command fails with `App not found: awesome-sauce`.

**Root cause:** The initial scoped policy only allowed `channel/*` and `release/*`. The CLI needs `kots/app/[]/read` to resolve the app slug to an internal app ID before it can access channels or releases.

**Fix:** Add `kots/app/[]/read` to the allowed resources. See the Recommended Policy Permissions table above.

### 2. App name vs. app slug mismatch

**Symptom:** Even with the correct `read` permission, the CLI still reports `App not found` when `--app awesome-sauce` is used.

**Root cause:** The app's **name** in the Vendor Portal was `awesome_sauce` (underscore), while the **slug** was `awesome-sauce` (hyphen). The Replicated CLI resolves `--app` against the name in some contexts, not the slug.

**Fix:** Rename the app in the Vendor Portal so the **name matches the slug exactly** (`awesome-sauce`). Once aligned, the CLI accepted the reference immediately.

**Takeaway:** Create the app with identical name and slug from the start. If they diverge, rename the app to match the slug rather than trying to work around it in `.replicated`.

### 3. Helm chart version must match promoted version label

**Symptom:** `release promote` fails with `Version label does not match any Helm charts in the release`.

**Root cause:** The workflow was passing the git SHA (`cdd3824...`) as `--version`, but the chart's `Chart.yaml` had `version: 0.1.0`. For Helm-based apps, the promoted version label must exactly match the chart version.

**Fix:** Read the chart version dynamically from `chart/Chart.yaml` and pass that to `release promote`:
```bash
chart_version=$(awk -F': ' '/^version:/ {print $2; exit}' chart/Chart.yaml)
replicated release promote <seq> <channel> --version "$chart_version"
```

### 4. `release test` requires a GitHub collab repo

**Symptom:** `replicated release test` returns `412: Team does not have a collab repo configured. Please contact support.`

**Root cause:** `release test` is designed to open a test issue in a linked GitHub repository. If no collab repo is configured in the Vendor Portal, the command fails.

**Fix (optional):** Configure a GitHub Collab Repo in the Vendor Portal app settings. If you don't need automated test issues, make the test step non-blocking in the workflow so the overall job still succeeds.

## References

- [Replicated Docs: Configure RBAC Policies](https://docs.replicated.com/vendor/team-management-rbac-configuring)
- [Replicated Docs: RBAC Resource Names](https://docs.replicated.com/vendor/team-management-rbac-resource-names)
- [Replicated Docs: Recommended CI/CD Workflows](https://docs.replicated.com/vendor/ci-workflows)
