# Postgres / PgBouncer dev TLS certificates (P0-8, H-4)

The dev TLS material for the `docker-compose.production.yml` stack
(`infrastructure/postgres/certs/`: internal CA + postgres + pgbouncer
server certs) is **generated at stack boot** — no certificate or key is
committed to git.

## How it works

- Canonical generator: `infrastructure/postgres/ssl-setup.sh` (openssl;
  idempotent — a set that is fresh for more than
  `RENEW_THRESHOLD_DAYS` (30) days is left untouched).
- Boot wiring: the one-shot `tls-certs-init` service in
  `docker-compose.production.yml` runs the script into the bind-mounted
  `infrastructure/postgres/certs/` and hands the artifacts to the
  postgres user (UID 70). `postgres` and `pgbouncer` gate on its
  successful completion (`service_completed_successfully`), and the
  postgres initdb script `04-ssl-copy.sh` copies the material into
  PGDATA with the right ownership — so every bring-up path
  (`docker compose up`, Makefile targets, scripts) gets certificates
  with no manual step.

## Operations

| Task | Command |
|---|---|
| Regenerate (e.g. key compromise) | `bash infrastructure/postgres/ssl-setup.sh --force` then restart `postgres` + `pgbouncer` |
| Manual boot generation (e.g. init service skipped) | `bash infrastructure/postgres/ssl-setup.sh` |
| Inspect validity | `openssl x509 -in infrastructure/postgres/certs/postgres.crt -noout -dates -subject -ext subjectAltName` |
| Verify chain | `openssl verify -CAfile infrastructure/postgres/certs/ca.crt infrastructure/postgres/certs/postgres.crt` |

Notes:

- **Never commit keys.** `infrastructure/postgres/certs/` is gitignored;
  the P0-8 pin (`scripts/tests/test_p08_dev_tls_boot_generation.py`,
  CI lint list) fails when any TLS artifact is tracked.
- The internal CA is for inter-service TLS only (Postgres ↔ PgBouncer ↔
  Django) — not a public CA. `ca.key` must stay secret; `ca.crt` is
  safe to distribute to verifying clients.
- Production (helm/k8s) does NOT use this directory: postgres is AWS
  RDS and pgbouncer's TLS material comes from Kubernetes secrets — the
  same pin asserts no helm artifact references the dev cert dir.
- Certificates are valid 10 years (3650 days), matching the CA; rotate
  via `--force` when the CA expires or a key is compromised (the W0.5
  rotation precedent: regenerate + re-verify + record in the rotation
  record for GATE-51).
