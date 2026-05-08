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

## References

- [Replicated Docs: Configure RBAC Policies](https://docs.replicated.com/vendor/team-management-rbac-configuring)
- [Replicated Docs: RBAC Resource Names](https://docs.replicated.com/vendor/team-management-rbac-resource-names)
- [Replicated Docs: Recommended CI/CD Workflows](https://docs.replicated.com/vendor/ci-workflows)
