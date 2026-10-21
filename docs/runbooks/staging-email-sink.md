# Staging email sink (MailHog)

**Phase 226 OQ-MailHog (resolved 2026-04-26)** — context for reviewers and on-call.

## TL;DR

Staging routes ALL outbound email through an in-cluster MailHog
StatefulSet (`hub-staging-mailhog`, helm values at
[helm/values.staging.yaml](../../helm/values.staging.yaml) under the
`mailhog:` block). The Django app's SMTP target (`SMTP_HOST=hub-staging-mailhog`,
`SMTP_PORT=1025`) is set on both the `api` and `worker` Deployments.
The MailHog inbox is exposed to the test runner via a token-gated read-only
proxy at:

```
GET https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog/api/v1/messages
GET https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog/api/v1/messages<id>/
```

with `X-E2E-Token: $STAGING_E2E_TEST_SECRET`. **Production never deploys
MailHog** (`mailhog.enabled: false` is the chart default), and even if it
did the proxy view is gated by `is_e2e_environment()` so reads stay 404.

## Architecture

```
                                      ┌─────────────────────────────────┐
                                      │  Worker Deployment              │
                                      │  ──────────────                 │
                                      │  send_password_reset_email      │
                                      │       │ Celery task             │
                                      │       ▼                         │
 GitHub Actions ─┐                    │  smtp.send → hub-staging-       │
 (Playwright)    │                    │              mailhog:1025       │
                 │  X-E2E-Token       └─────────────────────────────────┘
                 ▼                              │
 ┌────────────────────────┐                     │ SMTP (1025/TCP)
 │  Django proxy view     │                     ▼
 │  /api/v1/test/mailhog  │           ┌──────────────────────┐
 │  ────────────────────  │   HTTP    │  hub-staging-mailhog │
 │  is_e2e_environment    │──────────►│  ──────────────────  │
 │  verify_e2e_token      │  8025     │  in-memory inbox     │
 │  GET /api/v1/messages  │           │  (Deployment, 1 rep) │
 └────────────────────────┘           └──────────────────────┘
```

E2E SPARQL determinism rests on two contracts (NetworkPolicy + token gate):

1. **Network isolation.** [allow-mailhog-from-api-and-worker.yaml](../../helm/templates/networkpolicy/allow-mailhog-from-api-and-worker.yaml)
   restricts MailHog ingress to `component: api` (HTTP 8025 + SMTP 1025) and
   `component: worker` (SMTP 1025 only). No other in-cluster pod can reach it,
   and there is NO Ingress mapping — external access is exclusively via the
   Django proxy.
2. **Token gate.** Reads through the proxy require
   `X-E2E-Token: $STAGING_E2E_TEST_SECRET` (HMAC-equality-checked via
   the shared `verify_e2e_token` in [hub/apps/api/e2e_gating.py](../../hub/apps/api/e2e_gating.py)).
   The proxy strips this token + `Authorization` + `Cookie` before contacting
   MailHog (defence-in-depth: a compromised MailHog never sees Meshant
   credentials).

## Security model

**Trust boundary.** Anyone with `STAGING_E2E_TEST_SECRET` can read every
email staging emits — password-reset tokens, invitation links, plan-limit
notifications. This is the same boundary as the existing `ensure_e2e_*` /
`webhook-sink` family of test-only endpoints.

**Rotation.** When rotating `STAGING_E2E_TEST_SECRET`:
1. Update the GitHub repo secret (Settings → Secrets and variables → Actions).
2. Redeploy the staging chart so the `E2E_TEST_SECRET` env var on the api/worker
   pods picks up the new value (handled by ExternalSecrets refresh on next
   sync).
3. Optionally `kubectl rollout restart deploy/hub-staging-mailhog` to clear
   the inbox (otherwise the daily prune CronJob handles cleanup at 06:00 UTC).

**⚠️ Caveat — staging usage assumption.** This setup assumes staging is
test-only and that no real users sign up there. **If staging ever doubles
as a demo / UAT environment for stakeholders, a real user's password-reset
or invitation email lands in MailHog and is readable by anyone with
`STAGING_E2E_TEST_SECRET`.** Either:
- Confirm staging stays test-only, OR
- Roll back: set `mailhog.enabled: false` and revert the `EMAIL_BACKEND` /
  `SMTP_*` overrides in [helm/values.staging.yaml](../../helm/values.staging.yaml)
  (or override `EMAIL_BACKEND: "ses"` to restore real outbound delivery).
  The chart's Helm rollout applies cleanly without further surgery.

## Manual debugging

### From inside the cluster

```bash
# List recent inbox
kubectl -n hub-staging exec deploy/hub-staging-mailhog -- \
    wget -qO- http://localhost:8025/api/v1/messages

# Get a single message
kubectl -n hub-staging exec deploy/hub-staging-mailhog -- \
    wget -qO- http://localhost:8025/api/v1/messages/<message-id>

# Manually clear the inbox (the daily CronJob does this at 06:00 UTC)
kubectl -n hub-staging exec deploy/hub-staging-mailhog -- \
    wget -qO- --method=DELETE http://localhost:8025/api/v1/messages
```

### From outside the cluster (token-gated)

```bash
export TOK="$STAGING_E2E_TEST_SECRET"
curl -fsS -H "X-E2E-Token: $TOK" \
    https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog/api/v1/messages \
    | jq '.items | length'

curl -fsS -H "X-E2E-Token: $TOK" \
    "https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog/api/v1/messages<id>/" \
    | jq '.Content.Body'
```

If either returns 404, the gate failed: confirm token matches
`settings.E2E_TEST_SECRET` on the API pod, ENVIRONMENT is `staging`, and
the proxy view is mounted (`kubectl logs deploy/hub-staging-api | grep mailhog`).

If the inner read returns 503, MailHog is unreachable from the API pod:
check the NetworkPolicy and `kubectl get pods -l app.kubernetes.io/component=mailhog`.

## Inbox retention

MailHog runs with `-storage memory` (no persistence). Pod restart drops
the inbox; the daily CronJob at
[helm/templates/cronjob/mailhog-prune.yaml](../../helm/templates/cronjob/mailhog-prune.yaml)
issues `DELETE /api/v1/messages` against the in-cluster Service every 06:00 UTC
(off-peak vs the 02:30 UTC nightly E2E run) to keep memory bounded under
nominal load. The CronJob uses `curlimages/curl:8.6.0` and runs as a
non-root user with a read-only root filesystem.

## Why this setup (vs. alternatives)

This is **Path A** of three considered in the OQ-MailHog plan:

- **Path A (chosen)** — Real SMTP path goes to MailHog; proxy reads the inbox.
  Exercises the full SMTP code path including the Celery `send_password_reset_email`
  task. Best signal for catching email-emission regressions.
- **Path B** — Conditional routing (only `@example.com` recipients to MailHog,
  rest to real SES). Adds custom routing code that has its own audit
  surface; deferred unless staging stops being test-only.
- **Path C** — Backend hatch that returns the plaintext token directly.
  Smallest implementation but bypasses SMTP entirely, so a regression in
  `send_password_reset_email` would go undetected. Rejected.

## Future work

- **Mailpit substitution.** `mailhog/mailhog:v1.0.1` is from 2020 and the
  upstream project is archived. Mailpit (`axllent/mailpit`) is the
  maintained fork with drop-in v1 API compat, basic auth, and active
  security patches. Migration is a one-line image swap once we're ready
  to validate the JSON shape parity for our specific consumer.
- **Persisted inbox** — currently memory-only. If a future use case wants
  to retain mail across pod restarts (e.g. forensic replay of an
  intermittent flake), switch the deployment to `-storage maildir` with
  a PVC. Out of scope for the current spec.
