# Security

**Last Updated**: 2026-01-28

This document covers production security requirements: secrets, CORS, and related configuration.

---

## 1. Secrets in production and staging

### Requirements

- **Production and staging MUST set** `SECRET_KEY` and `JWT_SECRET_KEY` via environment (or a secret manager). They MUST NOT use the development default values.
- **Never commit** production or staging secrets to the repository.
- Use a secret manager (e.g. HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager) or CI/CD–injected environment variables for production/staging.

### Enforcement

- When `ENVIRONMENT=production`, Django startup fails with `ImproperlyConfigured` if:
  - `SECRET_KEY` is unset or equals the dev default (`dev-secret-key-not-for-production`), or
  - `JWT_SECRET_KEY` is unset or equals the dev default (`dev-jwt-secret-key-not-for-production`).
- Integration tests in `tests/security/test_production_secrets.py` assert that production rejects dev-default secrets and accepts non-default values (no mocks).

### How to set

- **Docker Compose**: Set in `.env` (never commit production `.env`) or pass via `environment:` in compose.
- **Kubernetes**: Use `Secret` resources and reference via `envFrom` or `valueFrom.secretKeyRef`.
- **CI/CD**: Inject from your secret store into the runtime environment; do not log or echo secrets.

### References

- `hub/settings.py`: `ENVIRONMENT`, `SECRET_KEY`, `JWT_SECRET_KEY`, and production validation block.
- `docs/DEVELOPMENT_GUIDE.md`: Production deployment and secrets overview.

---

## 2. CORS in production and staging

### Requirements

- In **production and staging**, CORS MUST use **explicit allowed origins**, not `*`.
- **Django**: `CORS_ALLOWED_ORIGINS` must list the exact origins (e.g. `https://app.example.com`, `https://hub.example.com`). Do not use `CORS_ALLOWED_ORIGINS=*` or allow-all when credentials (cookies, authorization headers) are used.
- **Traefik**: In `infrastructure/traefik/dynamic/routes.yml`, the CORS middleware `accessControlAllowOriginList` must not be `*` in production; replace with explicit origins (see file comments and deployment docs).

### How to set (Django)

- Set `CORS_ALLOWED_ORIGINS` as a comma-separated list or JSON array of origins, e.g.:
  ```bash
  CORS_ALLOWED_ORIGINS=https://app.example.com,https://hub.example.com
  ```
- For staging, use staging frontend/origin URLs only.
- See `hub/settings.py` for the default (development) list; production must override with explicit origins.

### How to set (Traefik)

- The file `infrastructure/traefik/dynamic/routes.yml` contains a CORS middleware with a placeholder `*` and a comment that production must replace it with explicit origins.
- For env-driven or deployment-specific CORS, generate this file from a template (e.g. CI/CD or ConfigMap) that injects the allowed origins for the environment.
- Traefik v3 file provider does not support env var substitution inside YAML; use a pre-processing step or separate generated file per environment.

### Validation

- **Checklist**: Before deploying to production/staging, confirm that `CORS_ALLOWED_ORIGINS` (Django) and Traefik CORS config do not use `*` when credentials are used.
- **CI**: Run `python scripts/check_production_cors.py --production` (or with `ENVIRONMENT=production`). It exits 1 if Traefik uses `accessControlAllowOriginList: ["*"]` or if Django `CORS_ALLOWED_ORIGINS` contains `*` when `ENVIRONMENT=production`. Add this to CI for production/staging builds.

---

## 3. AllowAny (public) endpoints

All views that use `AllowAny` are listed and reviewed in **`docs/AUDIT_POLICY.md`** (Section 3). For each endpoint we state whether it is intentional and what data is exposed. Public endpoints must **not** expose sensitive data (PII, tenant internals, secrets). Tests in `tests/security/test_allowany_public_endpoints.py` assert that unauthenticated access returns only intended public data.

---

## 4. Summary

| Item | Development | Production / Staging |
|------|-------------|----------------------|
| `SECRET_KEY` | Default allowed | MUST set via env; MUST NOT be dev default |
| `JWT_SECRET_KEY` | Default allowed | MUST set via env; MUST NOT be dev default |
| CORS (Django) | Default list or `*` for local | Explicit origins only |
| CORS (Traefik) | `*` acceptable for local | Explicit origins only |
| AllowAny endpoints | See `docs/AUDIT_POLICY.md` | Must not expose sensitive data; tests in `tests/security/test_allowany_public_endpoints.py` |
