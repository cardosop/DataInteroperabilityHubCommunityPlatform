# MVP test secrets — rotation policy

Phase 216.X.7 — defines how Phase 216 test infrastructure handles
secrets, where they live, and how they rotate.

## Storage

| Environment | Location | How loaded |
|---|---|---|
| Local dev | `.env.test` (gitignored) | `docker compose --env-file .env.test up -d` |
| CI (GitHub Actions) | GitHub Actions encrypted secrets | `env:` block in workflow yml |
| CI (Jenkins, future) | Vault → AWS Secrets Manager | Phase 211 vault-to-aws-secrets-manager |

`.env.test.example` in the repo root is the **template** — copy it to
`.env.test` (which is gitignored) and fill in real values from your
password manager. **Never commit `.env.test`.** A pre-commit hook
(`scripts/precommit/check_no_secrets.sh`, Phase 218) blocks any commit
that introduces a `.env.test` path.

## What lives in `.env.test`

* `POSTGRES_TEST_USER` / `POSTGRES_TEST_PASSWORD` — local docker compose only
* `MESHANT_API_URL_MVP` / `MESHANT_API_URL_FULL` — backend URLs (not secret, but env-bound)
* `TEST_API_KEY` / `DATAHUB_API_KEY` — SDK/CLI integration test API keys
* `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` — local object storage
* `STRIPE_SECRET_KEY_TEST` — Stripe test mode key (sk_test_*)

The full set is enumerated in `.env.test.example`.

## Rotation cadence

| Secret | Cadence | Owner | Process |
|---|---|---|---|
| `TEST_API_KEY` | **quarterly** | Platform team | `python manage.py rotate_test_api_keys` (deferred to Phase 218) |
| `DATAHUB_API_KEY` | **quarterly** | Platform team | Same command |
| `STRIPE_SECRET_KEY_TEST` | on Stripe-side rotation | Billing team | Manual: copy from Stripe dashboard, update GH secret, update password manager |
| `MINIO_ROOT_PASSWORD` | **quarterly** | Platform team | Manual: regenerate, update `.env.test.example` placeholder, update CI |
| `POSTGRES_TEST_PASSWORD` | local only | n/a | n/a (no production reach) |

Quarterly cadence = Q1 (Mar-15), Q2 (Jun-15), Q3 (Sep-15), Q4 (Dec-15).

A calendar reminder is owned by the Platform team rotation manager.
Failure to rotate by deadline + 7 days triggers a P2 incident under
the project's `RUNBOOK_INCIDENT_RESPONSE.md` (deferred to Phase 217.3).

## Rotation procedure (TEST_API_KEY example)

1. Generate a new key: `python manage.py rotate_test_api_keys --create-only --label="Q1-2026"` against the staging hub. The command emits the new key to stdout once and never again.
2. Update GitHub Actions secret: `gh secret set TEST_API_KEY < new_key.txt`
3. Update the team password manager entry.
4. Update `.env.test` for every developer who runs the integration suite locally (announcement in #platform-eng Slack).
5. After 24 hours of green CI on the new key, revoke the old key: `python manage.py rotate_test_api_keys --revoke=<old_key_label>`
6. Update this document's "last rotated" log below.

## Rotation log

| Date (UTC) | Secret | Actor | Notes |
|---|---|---|---|
| 2026-04-08 | (initial) | Phase 216.X.7 author | Doc created |

## Out of scope (deferred to Phase 218)

* Automated `rotate_test_api_keys` management command — Phase 218
* Vault → AWS SM migration for prod secrets — Phase 211 (separate spec)
* Pre-commit hook `check_no_secrets.sh` — Phase 218
* Secret-scanning GH Action (truffleHog / gitleaks) — Phase 218
