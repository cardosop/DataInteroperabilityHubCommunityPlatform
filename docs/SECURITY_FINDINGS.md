# Security Findings

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26
**Status**: Active

---

## Pen Test Scope

### In-Scope

- API endpoints (all `/api/v1/` routes)
- Authentication and authorization flows (JWT, refresh tokens, API keys)
- Tenant isolation boundaries
- File upload/download operations
- SSRF protection on external ref resolution
- Webhook secret management
- Rate limiting and brute-force protections

### Out of Scope

- Third-party SaaS integrations (Prefect Cloud, external marketplaces)
- Cloud infrastructure (AWS/GCP control plane)
- Physical security

## Remediation SLA

| Severity | Remediation SLA | Escalation              |
|----------|-----------------|-------------------------|
| Critical | 7 days          | Immediate hotfix        |
| High     | 14 days         | Next sprint             |
| Medium   | 30 days         | Backlog prioritization  |
| Low      | 90 days         | Best effort             |

## CI/CD Security Controls

The following security scanning tools are integrated into CI:

- **Bandit** — Python static analysis for security issues
- **Trivy** — Container image vulnerability scanning (CRITICAL+HIGH block)
- **pip-audit** — Python dependency vulnerability scanning
- **eslint-plugin-security** — Frontend JavaScript security linting
- **SAST** — CodeQL analysis on pull requests

## Findings Register

| ID   | Date       | Severity | Description                          | Status     | Remediation                     |
|------|------------|----------|--------------------------------------|------------|---------------------------------|
| SF-1 | 2026-02-15 | High     | Webhook secrets stored in plaintext  | Resolved   | Fernet encryption (v1: prefix)  |
| SF-2 | 2026-02-20 | Medium   | Missing SSRF protection on ref resolver | Resolved | IP blocklist + DNS rebinding guard |
| SF-3 | 2026-03-01 | High     | Refresh token not rotated on use     | Resolved   | Family rotation with replay detection |
| SF-4 | 2026-03-10 | Medium   | No rate limit on login endpoint      | Resolved   | IP-based rate limiting + account lockout |

## Risk Acceptance Register

| ID   | Description                                         | Accepted By  | Date       | Review Date |
|------|-----------------------------------------------------|-------------|------------|-------------|
| RA-1 | Redis cache does not use TLS in dev/staging         | Backend Lead | 2026-03-15 | 2026-06-15  |
| RA-2 | Vault dev mode used in local development            | Backend Lead | 2026-03-15 | 2026-06-15  |
