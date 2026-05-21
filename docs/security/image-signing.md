# Image Signing (Phase 7.3)

**Status:** Live as of chart `0.3.36` (2026-05-21).
**Approach:** Keyless cosign signing via GitHub Actions OIDC → Sigstore Fulcio.

## How it works

Every container image we publish to GHCR is signed automatically by CI. The signing happens immediately after the image push, in `.github/workflows/images.yml`. The signing identity is ephemeral and bound to the workflow run that produced the image — there are no long-lived signing keys to manage, rotate, or compromise.

The full chain:

1. CI builds the image and pushes to GHCR.
2. CI installs cosign via `sigstore/cosign-installer@v3`.
3. CI calls `cosign sign --yes <repo>@<digest>` for each published image.
4. Cosign requests an ephemeral signing certificate from Sigstore Fulcio, presenting a GitHub Actions OIDC token as proof of identity. The certificate is bound to the workflow + commit SHA + branch + trigger that produced the image.
5. Cosign signs the image digest with the ephemeral private key.
6. The signature + certificate + bundle are uploaded to the public Sigstore Rekor transparency log (so anyone in the world can verify the signature is from us, and that we can't quietly un-publish a signature later without leaving evidence in the log).
7. The signature is stored as an OCI artifact alongside the image in GHCR, addressable as `<image>.sig` and discoverable by cosign automatically.

The ephemeral key is destroyed at the end of the signing operation. There is no `cosign.key` file in this repository or in any CI secret.

## Verification

To verify any of our signed images:

```bash
cosign verify ghcr.io/seanoseanohay/replicated2-backend:0.3.36 \
  --certificate-identity-regexp='^https://github\.com/seanoseanohay/replicated2/.+' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com'
```

The `--certificate-identity-regexp` constrains the verifier to "the signature must have been produced by a workflow in the `seanoseanohay/replicated2` GitHub repository." The `--certificate-oidc-issuer` constrains to "the OIDC issuer must be GitHub Actions." Together they say *"this image was signed by a real GitHub Actions run of our actual repository, not by anyone else."*

A passing verification returns the signed claims as a JSON object including:

| Field | Meaning |
|---|---|
| `critical.identity.docker-reference` | The repo path the signature applies to. |
| `critical.image.docker-manifest-digest` | The exact digest signed (e.g. `sha256:39a24aae...`). Signatures are bound to digests, not tags. |
| `optional.Issuer` | Always `https://token.actions.githubusercontent.com` for our signatures. |
| `optional.Subject` | The full workflow URL: `https://github.com/seanoseanohay/replicated2/.github/workflows/images.yml@refs/heads/<ref>` |
| `optional.githubWorkflowName` | `Build and Push Images` |
| `optional.githubWorkflowSha` | The git SHA of the commit that triggered the build. |
| `optional.githubWorkflowTrigger` | `push` / `workflow_dispatch` / etc. |
| `optional.Bundle.Payload.integratedTime` | Unix timestamp when the signature landed in Sigstore's transparency log. |
| `optional.Bundle.Payload.logIndex` | Index into Sigstore's Rekor log — a globally-unique receipt anyone can look up. |

This means a verifier downstream of us can prove not just "Lawrence signed this" but "**THIS specific workflow run, on THIS specific commit, on THIS specific branch, at THIS specific time, signed THIS exact image**." That's a much stronger property than traditional signing-key models.

## Threat model and what this protects against

Image signing addresses **supply chain integrity**, not application-layer security.

| Threat | Does image signing help? |
|---|---|
| Attacker pushes a malicious image to our GHCR repo (e.g., via a leaked GitHub token) | ✅ Yes — the unauthorized image won't have a valid signature from our workflow identity, so a verifier with the correct constraints will reject it. |
| Attacker compromises our build workflow (e.g., malicious PR merged that publishes a backdoored image) | ❌ No — the malicious image gets signed by our workflow because the workflow itself is the attacker. (Mitigations: code review, branch protection, restricted workflow permissions — outside the scope of signing.) |
| Attacker compromises the customer's `helm pull` infrastructure (e.g., MitM) | ✅ Yes — if the customer verifies signatures during pull, a substituted image will fail verification. |
| Attacker replays an old signed-but-vulnerable image to a customer | ⚠️ Partial — signing alone doesn't prevent replay; combine with policy ("only accept images newer than X") or with a chart-pinned digest reference. |
| Attacker tampers with the image at rest in GHCR | ✅ Yes — any byte-level modification changes the digest, breaking the signature binding. |
| Application-level CVEs in the image | ❌ No — signing says nothing about what's inside the image. See `docs/security/cve-posture.md` for the CVE story. |

## Why keyless and not key-based

The alternative is to generate a long-lived signing key, store it in a CI secret, and sign with it. Two reasons we don't do that here:

1. **Key management is a separate ongoing operational concern.** Where do we store the private key? Who has access? When do we rotate it? What's the recovery story if the secret is leaked? Each of those decisions is a place to get something wrong. Keyless eliminates all of it.
2. **Bound provenance is a stronger property than identity-only signing.** A long-lived key proves "someone with the key signed this." Keyless proves "this specific workflow run on this specific commit signed this." The keyless model carries more useful information for a downstream verifier.

Tradeoff: keyless requires internet access to Sigstore (Fulcio + Rekor) during the sign and verify operations. Air-gapped signing is not possible with the keyless flow — for an air-gapped environment a key-based approach (with a HSM, hardware key, or KMS) is the right answer. Our current CI is internet-connected, so keyless is the cleanest fit.

## What was changed for 7.3

`.github/workflows/images.yml`:

```yaml
permissions:
  contents: read
  packages: write
  id-token: write    # NEW: required so the workflow can request an OIDC
                     # token from GitHub for Sigstore authentication.

# ... existing build-push-action steps now have explicit `id:` so we can
#     reference their `digest` output. Backend/worker/beat are built once
#     from the same Dockerfile and share a manifest digest; the frontend
#     is its own digest.

      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign backend, worker, and beat images (keyless via GitHub OIDC → sigstore)
        env:
          DIGEST: ${{ steps.build-backend-family.outputs.digest }}
          OWNER: ${{ github.repository_owner }}
        run: |
          for image in replicated2-backend replicated2-worker replicated2-beat; do
            cosign sign --yes "ghcr.io/${OWNER}/${image}@${DIGEST}"
          done
```

And an analogous step in the `build-frontend` job.

## Verified result for chart 0.3.36

All four images signed and verifiable as of 2026-05-21:

```
ghcr.io/seanoseanohay/replicated2-backend:0.3.36   → signed by workflow run 9346038
ghcr.io/seanoseanohay/replicated2-worker:0.3.36    → signed by workflow run 9346038
ghcr.io/seanoseanohay/replicated2-beat:0.3.36      → signed by workflow run 9346038
ghcr.io/seanoseanohay/replicated2-frontend:0.3.36  → signed by workflow run 9346038
```

Backend signature claims (representative output from `cosign verify`):

```
Subject:               https://github.com/seanoseanohay/replicated2/.github/workflows/images.yml@refs/heads/master
Issuer:                https://token.actions.githubusercontent.com
githubWorkflowName:    Build and Push Images
githubWorkflowSha:     9346038955edadec787d240fdd4162de29583b6d
githubWorkflowRepo:    seanoseanohay/replicated2
githubWorkflowTrigger: push
manifestDigest:        sha256:39a24aae6e869c340034a011332a28f4ff1978d65d45271ef237b9822273e484
rekorLogIndex:         1594206743
```

Anyone in the world can independently audit this signature by:

1. Cloning a copy of cosign
2. Running the verify command above
3. Looking up Rekor log index 1594206743 at `https://search.sigstore.dev/?logIndex=1594206743`

## Forward / not backward

Per the 7.3 implementation decision, images at chart versions **before** 0.3.36 are not signed retroactively. The signing applies forward from 0.3.36. If we ever want to backfill, cosign can sign existing images by digest; the limiting factor would be that we'd be signing them today (so the workflow identity in the certificate would say "2026-05-21" not whenever the image was originally built), which is a slightly degraded provenance story. We accepted this tradeoff to keep the work scoped.

## Policy options for downstream consumers

The signed images alone don't enforce anything — a customer who pulls them and doesn't verify will still get the bytes regardless. Customers (or our own deployment processes) who want to enforce "only deploy signed images" have options:

- **Kyverno** or **OPA Gatekeeper** policies with `cosign verify` admission rules.
- **Sigstore Policy Controller** specifically designed for keyless signature admission in Kubernetes.
- **CMX network policy** + manual `cosign verify` during install verification.

These are outside the scope of 7.3 ("sign your images") but are the natural follow-up if someone asks "and how do my customers actually USE the fact that the images are signed."
