# Secrets Rotation — Phase 313.0 (2026-08-13)

OpenSpec: `openspec/changes/preprod01/tasks.md` → 313.0.1 / 313.0.2.
Plan: `/home/ph/.claude/plans/velvet-jingling-thacker.md` → Phase 0.

## What leaked

| Artifact | Where | Exposure |
|---|---|---|
| `SECRET_KEY` (one key shared by dev + staging) | tracked `.env.dev` / `.env.staging` | history commits `7787cdcd`, `e4edc3cb` (2 hits) |
| Staging `POSTGRES_PASSWORD` + `DATABASE_URL` credentials | tracked `.env.staging` | history (5 / 1 hits) |
| `CKAN_DADOS_GOV_BR_API_KEY` (live JWT) | tracked `.env.test`, root `.env` | history: commits `054f8b35`, `ce527bb5`, `bb6251ce`, `88ba8814`, `7e5cb71a` |
| Provider test tokens (Snowflake, Azure, Stripe test key, AWS Data Exchange, Databricks, Athena, CKAN) | tracked `.env.test` | history (1–2 hits each) |
| Postgres/pgbouncer TLS private keys + CA | tracked `infrastructure/postgres/certs/*` | history (committed 2026-04-03) |
| MinIO/Fuseki/Grafana admin passwords shared across dev/staging | tracked `.env.dev` / `.env.staging` | history (3–4 hits each) |

Root cause: real secrets lived in **git-tracked files**, and dev/staging shared one key. Both fixed structurally (see below).

## What was rotated (repo-side — executed)

1. **Root-cause fix**: `.env.dev`, `.env.staging`, `.env.test` untracked (`git rm --cached`) and covered by `.gitignore` (Phase 313.0 comment block). Only templates/examples remain tracked: `.env.dev.template`, `.env.example`, `.env.local.example`, `.env.production.template`, `.env.test.example`.
2. **Fresh unique values per environment file** (never printed; generated via `secrets.token_urlsafe`): `SECRET_KEY` (64 chars, unique per file), `POSTGRES_PASSWORD` + embedded `DATABASE_URL` password (staging), MinIO root user/password + matching S3 credentials (per-file pair), `FUSEKI_ADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`.
3. **Provider tokens emptied** from `.env.test` and root `.env`: CKAN (test + dados.gov.br), Snowflake, Azure, Stripe test key, AWS Data Exchange, Databricks, Athena. Compose `${VAR:-fallback}` defaults take over for emptied infra values. Re-obtain from providers when paid-service integration tests are needed (checklist below).
4. **TLS regenerated** (`infrastructure/postgres/certs/`): new CA + pgbouncer/postgres leaves, RSA-4096, same CN/SAN contract (`DNS:pgbouncer|postgres`, `localhost`, `hub-*-production`, `hub-staging-*`, `127.0.0.1`), 3650 days, `openssl verify` chain OK, private keys 0600.
5. **Verification suite (TDD)**: NEW `tests/security/test_secrets_rotation.py` — 5 tests, no mocks (real git/gitleaks/openssl):
   - no real env file is git-tracked (regression guard for the root cause)
   - local env secret values absent from git history (incl. non-local `DATABASE_URL` credentials)
   - secret values unique across env files (the shared-key sin never returns)
   - TLS material absent from history + valid + CN/SAN contract preserved
   - gitleaks clean on the tracked tree (skips when CLI absent — CI runs gitleaks-action)
   History-based tests skip on shallow clones (CI fetch-depth 1); the publish pipeline re-runs them against full history.
6. **Backstops**: pre-commit `gitleaks` hook (skips cleanly when CLI absent); `.gitleaks.toml` local-env path allowlist (`^\.env($|\..*$)` — re-tracking is blocked independently by the test above); CI `gitleaks/gitleaks-action@v2` unchanged; GitHub secret-scanning push protection to enable on the repo (settings step below).

## Review fixes (2026-08-14)

Adversarial review found and fixed one regression introduced by the rotation, plus two pre-existing defects:

1. **Compose interpolation regression (introduced by 313.0, FIXED)**: root `.env` is docker-compose's **interpolation source** (`${POSTGRES_PASSWORD:?...}` etc.) while api containers read `.env.dev` via `env_file:`. The rotation emptied root `.env` infra keys → `docker compose -f docker-compose.yml config` failed with "required variable MINIO_ROOT_PASSWORD is missing". Root cause fix: root `.env` now **mirrors the `.env.dev` infra credentials** (POSTGRES_PASSWORD, MINIO_ROOT_USER/PASSWORD, AWS S3 pair, FUSEKI_ADMIN_PASSWORD, GRAFANA_ADMIN_PASSWORD) — duplication is by design, not the shared-key sin (which was cross-environment dev↔staging). Regression guards added to the suite: `test_root_env_mirrors_dev_environment`, `test_dev_compose_resolves_after_rotation`, `test_test_compose_resolves_after_rotation`, `test_dev_compose_credentials_consistent_with_env_dev` (compose tests carry `docker_compose_runtime` and skip without the docker CLI).
2. **Staging compose required vars (PRE-EXISTING, documented, not introduced)**: `docker-compose.staging.yml` requires `PGBOUNCER_ADMIN_PASSWORD` (`:?`) which root `.env` never carried — local staging-compose `config` was already broken before 313.0 (evidence: pre-rotation key inventory). Deployed staging is Helm/ExternalSecrets-driven (313.0.3). If local staging compose is used, provide `PGBOUNCER_ADMIN_PASSWORD` etc. — see checklist item 8.
3. **Pre-commit hook defect (PRE-EXISTING, FIXED)**: `type-check-marketplace-code` declared `additional_dependencies` under `language: system`, which pre-commit 4.x rejects and which blocked the whole hook runner. Removed the invalid key (system hooks must have deps on PATH); `pre-commit validate-config` now passes and the new `gitleaks` hook runs green.

Repeatable verification: `scripts/verify_secrets_rotation.sh` (suite + gitleaks git-mode + scoped `--no-git` over the publishable surface). Override the interpreter with `PYTHON=venv/bin/python`.

## Verification evidence (repo-side)

- `pytest tests/security/test_secrets_rotation.py` → **9/9 passed** (TDD: RED 4 failed → rotate → GREEN; review round RED 3 → mirror fix → GREEN).
- `gitleaks detect` (git mode, CI parity) → **exit 0**.
- `gitleaks detect --no-git` over the tracked tree + local env files (scoped surface) → **exit 0**.
- Staging `DATABASE_URL` password rotated (24 chars, differs from dev — hash-verified).
- Old values remain in private git history **by design until Phase 313.3** (filter-repo scrub before the public mirror).

## Environment-side checklist (USER-EXECUTED — blocks anything public)

Tracked in tasks.md as 313.0.3. Complete in order; re-verify after each item.

1. **Invalidate at provider**: revoke the leaked `CKAN_DADOS_GOV_BR_API_KEY` JWT at dados.gov.br/CKAN (present in 5 history commits).
2. **Rotate deployed secrets** in ExternalSecrets/Vault for staging + production: `SECRET_KEY`, `JWT_SECRET_KEY` (plus a NEW RS256 keypair for `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` — see `hub/settings.py:1906-1909`), `ENCRYPTION_KEY`, Postgres passwords, MinIO/Fuseki/Grafana admin passwords. Do NOT reuse the dev/staging values generated in this rotation.
3. **Apply the new local staging values** (`DATABASE_URL` password + `POSTGRES_PASSWORD` in the untracked `.env.staging`) to the staging environment — or generate your own and overwrite the file. Never commit either.
4. **Deploy the new TLS material** to staging/production pgbouncer + postgres; redeploy both (clients must trust the new CA). The old cert keys are in history — do not roll back.
5. **Re-obtain provider test tokens** (CKAN, Snowflake, Azure, Stripe test key, AWS Data Exchange, Databricks, Athena) and set them in the local untracked `.env.test` when paid-service integration tests are needed. They remain empty until then.
6. **Enable GitHub settings**: secret scanning push protection + Dependabot alerts (also listed in the publish checklist, Phase 313.3).
7. **Re-verify**: `scripts/verify_secrets_rotation.sh` (or `pytest tests/security/test_secrets_rotation.py` + `gitleaks detect`) → all clean.
8. **If local staging compose is used**: provide the required interpolation vars it expects but root `.env` never carried (`PGBOUNCER_ADMIN_PASSWORD` and any other `:?`-required vars) — pre-existing gap, documented in "Review fixes". Prefer `--env-file .env.staging` so interpolation and container env come from one rotated source.

## Rollback notes

- Old values are intentionally NOT restored: they are compromised by history. If a rotated value breaks an environment, generate a NEW one — never revert to a leaked value.
- Expected until 313.3: `git log -S <old-value>` still matches historical commits. That is accepted per 313.0 acceptance ("matches only historical commits that will be scrubbed in 313.3") and closed by the filter-repo scrub.
- The verification suite is the standing regression guard — do not weaken it to make CI pass.
