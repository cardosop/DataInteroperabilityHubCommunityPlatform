# E2E Setup — the `X-E2E-Token` shared-secret gate

The four `/api/v1/test/ensure-e2e-*` endpoints are used by Playwright
fixtures to prime tenant subscriptions, mint invitation tokens, create
second tenants for tenant-switch tests, and reset E2E user accounts.
They write real data to real tables, so they are gated by a shared
secret comparison in addition to the environment check.

## The gate, at a glance

- Decorator: `@require_e2e_token` in `hub/apps/api/views.py`
- Setting: `settings.E2E_TEST_SECRET` (read by the decorator)
- Header: `X-E2E-Token` on the incoming request
- Comparison: `hmac.compare_digest` (constant-time)

Behavior matrix:

| `E2E_TEST_SECRET` | `X-E2E-Token` header | `ENVIRONMENT` | Response |
|---|---|---|---|
| empty / unset | any (or missing) | any | `404` unconditionally |
| set | missing | any | `404` |
| set | wrong | any | `404` + log `e2e_token_mismatch` at WARNING |
| set | correct | `production` | `404` (view-body env guard fires) |
| set | correct | `staging` / `test` / dev-with-DEBUG | normal view response |

## Where the secret lives

| Environment | Source | Mechanism |
|---|---|---|
| Staging pods | AWS Secrets Manager: `staging/hub/e2e` (JSON: `{"E2E_TEST_SECRET": "<uuid>"}`) | ExternalSecrets operator → K8s Secret `hub-secrets-staging` → `envFrom: secretRef:` → pod env |
| GitHub Actions (E2E workflow) | GitHub secret `E2E_TEST_SECRET` (mirror of AWS SM value) | workflow env → `process.env.E2E_TEST_SECRET` → Playwright headers |
| Local development | `hub/.env` (backend) + `frontend/.env.local` (Playwright) | Django `env.str()` + Playwright reads `process.env` |

Both sides must match — the secret value is case-sensitive and compared byte-for-byte.

## Local development

Any non-empty string ≥ 32 chars works locally (the secret is never shipped
to AWS SM for dev). Pick any memorable placeholder:

```bash
# In hub/.env (backend)
E2E_TEST_SECRET=dev-local-not-a-real-secret-32chars+

# In frontend/.env.local (Playwright)
E2E_TEST_SECRET=dev-local-not-a-real-secret-32chars+
```

Without these, local Playwright runs that hit `ensure-e2e-*` will 404.

## CI (GitHub Actions)

The `E2E_TEST_SECRET` GitHub secret must mirror the AWS SM value. Inside
the workflow:

```yaml
- run: echo "::add-mask::${{ secrets.E2E_TEST_SECRET }}"
- run: npx playwright test
  env:
    E2E_TEST_SECRET: ${{ secrets.E2E_TEST_SECRET }}
```

The `::add-mask::` directive ensures the secret is redacted from
workflow logs even if a step accidentally echoes it.

## Rotation procedure

1. **Generate a new UUID:**
   ```bash
   python3 -c "import uuid; print(uuid.uuid4().hex)"
   ```

2. **Update AWS Secrets Manager:**
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id staging/hub/e2e \
     --secret-string '{"E2E_TEST_SECRET":"<new-uuid-here>"}'
   ```

3. **Force-sync ExternalSecrets** (avoids 1-hour max drift on the
   staging refreshInterval, which is `1m` per values.staging.yaml but
   still worth nudging for immediate rotation):
   ```bash
   kubectl annotate externalsecret/hub-secrets-staging \
     force-sync=$(date +%s) --overwrite
   ```

4. **Update the GitHub Actions secret** (via the GitHub UI or `gh`):
   ```bash
   gh secret set E2E_TEST_SECRET --body '<new-uuid-here>'
   ```

5. **Restart API pods** so in-memory settings pick up the new value
   (a `kubectl rollout restart deployment/hub-api` works; the Reloader
   controller may handle this automatically depending on cluster config):
   ```bash
   kubectl rollout restart deployment/hub-staging-api
   kubectl rollout restart deployment/hub-staging-worker
   kubectl rollout restart deployment/hub-staging-worker-heavy
   ```

6. **Verify** with a manual probe:
   ```bash
   # Expect 200 (AllowAny + token + staging)
   curl -si -X POST \
     -H "X-E2E-Token: $NEW_SECRET" \
     -H "Content-Type: application/json" \
     -d '{}' \
     https://api.stagingmeshant-internal.example.com/api/v1/test/ensure-e2e-users/ \
     | head -1

   # Expect 404 (wrong token)
   curl -si -X POST \
     -H "X-E2E-Token: old-secret-should-not-work" \
     https://api.stagingmeshant-internal.example.com/api/v1/test/ensure-e2e-users/ \
     | head -1
   ```

## Post-deploy health check

The `hub.E001` and `hub.E002` Django system checks are registered with
`deploy=True`, so they run only on `manage.py check --deploy`. Wire this
as a post-deploy smoke step against a live pod:

```bash
kubectl exec deploy/hub-staging-api -- \
  python manage.py check --deploy --fail-level WARNING
```

Expected: exit code 0. If `hub.E001` fires, `MVP_MODE` is not set to
`True` on staging (check Helm values + CI `MVP_HELM_SETS`). If
`hub.E002` fires, `E2E_TEST_SECRET` is not populated (check ESO sync
and AWS SM secret existence).

## Observability

Every mismatched `X-E2E-Token` emits a WARNING log via the Django
logger `hub.apps.api.views`:

```
e2e_token_mismatch   path=/api/v1/test/ensure-e2e-users/   remote_addr=1.2.3.4   has_header=True
```

Neither the provided token nor the expected secret is ever logged.
Consider a Grafana alert on sustained non-zero rates — that's a clear
signal of staging probe traffic or a misconfigured CI.
