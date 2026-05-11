# TLS Certificate Setup

## Overview

The Bundle Analyzer Helm chart supports three TLS certificate modes for serving the application over HTTPS.

## Certificate Options

### 1. Automatically Provisioned (cert-manager / Let's Encrypt)

Requires cert-manager installed in the cluster with a configured ClusterIssuer.

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
  certManager:
    enabled: true
    clusterIssuer: letsencrypt-prod
  generateSelfSignedCert: false
  hosts:
    - host: bundlyzer.com
      paths:
        - path: /
          pathType: Prefix
```

### 2. Manually Uploaded Certificate

Two paths:

**Option A: Pre-created Kubernetes Secret**

```bash
kubectl create secret tls bundle-analyzer-tls \
  --cert=cert.pem --key=key.pem \
  -n <namespace>
```

```yaml
ingress:
  enabled: true
  tls:
    - hosts:
        - bundlyzer.com
      secretName: bundle-analyzer-tls
```

**Option B: Inline PEM in values.yaml**

```yaml
ingress:
  enabled: true
  tls:
    - hosts:
        - bundlyzer.com
      secretName: bundle-analyzer-tls
  # Then create the secret manually or use a separate Secret template
```

### 3. Self-Signed Certificate (Default for Testing)

```yaml
ingress:
  enabled: true
  generateSelfSignedCert: true
  regenerateSelfSignedCert: false   # Set true to force new cert on upgrade
  hosts:
    - host: bundlyzer.com
      paths:
        - path: /
          pathType: Prefix
```

**Important**: Self-signed certificates are now **persistent across Helm upgrades** thanks to the `lookup` function and `helm.sh/resource-policy: keep` annotation. The cert will only regenerate on:
- First install (no existing Secret)
- Explicit `helm upgrade --set ingress.regenerateSelfSignedCert=true`

## HTTPS Redirect

All TLS-enabled deployments automatically include the `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` annotation, which redirects HTTP→HTTPS at the Ingress level.

## Common Issues

### Chrome Shows "Not Secure" After Upgrade

**Cause**: Old `genSelfSignedCert` behavior regenerated the cert on every `helm upgrade`. Chrome cached the old cert fingerprint.

**Fix**: The chart now uses `lookup` to preserve existing self-signed certs. Run `helm upgrade` again — the cert serial will remain unchanged.

**Workaround if still seeing warning**: Force-quit Chrome completely (Cmd+Q on macOS) and restart.

### Mixed Content Errors

If the frontend calls the API over HTTP while the page is served over HTTPS, check that `VITE_API_URL` or the frontend's `BACKEND_URL` environment variable uses `https://`.

## Verification

```bash
# Check cert serial
echo | openssl s_client -connect bundlyzer.com:443 -servername bundlyzer.com 2>/dev/null | openssl x509 -noout -serial

# Verify HTTPS redirect
curl -I http://bundlyzer.com/login
# Should return: HTTP/1.1 308 Permanent Redirect -> https://...
```
