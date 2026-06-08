# Security Policy

**Contact:** security@meshant.com
**Last updated:** 2026-05-18 (Phase 285.8.2)

## Vulnerability Disclosure

Meshant takes security seriously. If you discover a vulnerability, please:

1. **Do NOT open a public issue or PR.** Disclose privately to security@meshant.com
2. Include: description, affected component, steps to reproduce, impact assessment
3. We will acknowledge within 24 hours and provide a timeline within 72 hours
4. We request a 90-day embargo before public disclosure

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ Full support |
| `staging` | ✅ Active testing |
| `v1.x` (GA) | ✅ Full support |
| `< v1.0` | ❌ Pre-release, no security patches |

## Scope

- API endpoints (`/api/v1/*`)
- Authentication and authorization (JWT, OAuth, SSO, MFA)
- Tenant isolation and RLS policies
- Credential handling (AWS SM, Prefect, dlt secrets)
- Container images and CI/CD pipeline
- Infrastructure (K8s, Traefik, PostgreSQL, Redis, Fuseki)

## Out of Scope

- Phishing attacks against meshant.com email
- Social engineering of employees
- Denial of Service (covered by WAF/rate limiting)

## Recognition

We maintain a security hall of fame for acknowledged reporters. With permission,
we will credit you in the release notes for the fixed version.

## SAST/DAST/Regression Testing Strategy

| Layer | Tool | Frequency | Gate |
|-------|------|-----------|------|
| **SAST** (Static) | Semgrep, Bandit, Ruff | Every PR | Blocks merge on HIGH/CRITICAL |
| **SCA** (Dependencies) | `pip-audit`, `npm audit`, Dependabot | Daily + every PR | Blocks on known CVE (CVSS ≥7) |
| **DAST** (Dynamic) | OWASP ZAP baseline scan | Weekly in staging | Alert on HIGH/CRITICAL |
| **Secrets** | `detect-secrets`, `truffleHog` | Pre-commit + CI | Blocks push on detected secret |
| **Container** | Trivy, Cosign | Every build | Blocks on CRITICAL CVE |
| **Regression** | `pytest` suite | Every PR | 0 failures on security tests |

## Data Classification Matrix

| Tier | Label | Examples | Encryption | Retention | Access |
|------|-------|----------|------------|-----------|--------|
| **P0** | Critical PII | Payment cards, SSN, health records | Field-level + TLS | 90 days max | PLATFORM_ADMIN only |
| **P1** | Sensitive PII | Email, phone, address, name | Field-level + TLS | Per retention policy | TENANT_ADMIN + DPO |
| **P2** | Business Confidential | Contracts, pricing, ODPS specs | TLS at rest + transit | Per contract | Tenant-scoped RBAC |
| **P3** | Internal | Logs, metrics, audit events | TLS at rest | 3 years (audit) | Admin roles |
| **P4** | Public | Product docs, API specs | None | Indefinite | Public |

## Quarterly Access Review

1. **Admin roles:** Export PLATFORM_ADMIN + TENANT_ADMIN user list. Review and deactivate stale accounts.
2. **API keys:** `SELECT id, user_id, created_at FROM baas_api_keys WHERE revoked_at IS NULL`. Rotate keys >365 days.
3. **Service accounts:** Audit `INTERNAL_API_KEY` usage. Rotate quarterly.
4. **AWS IAM:** Review IAM roles with `secretsmanager:GetSecretValue`. Remove unused.
5. **K8s RBAC:** `kubectl auth can-i --list` for all service accounts.

## OWASP Top 10 Compliance

| OWASP 2021 | Control | Status |
|-----------|---------|--------|
| A01: Broken Access Control | RLS policies, tenant isolation, ABAC | ✅ |
| A02: Cryptographic Failures | KMS + Fernet encryption, TLS 1.3 | ✅ |
| A03: Injection | Parameterized queries, input validation, SSRF guard | ✅ |
| A04: Insecure Design | Threat modeling, security review per phase | ⚠️ Ongoing |
| A05: Security Misconfiguration | CSP headers, PSS, CIS benchmarks | ⚠️ 285.8.2.5 planned |
| A06: Vulnerable Components | `pip-audit`, `npm audit`, Dependabot | ✅ |
| A07: Auth Failures | MFA (285.8.1.1), token rotation, rate limiting | ⚠️ 285.8.3.5 planned |
| A08: Software/Data Integrity | Cosign (285.8.1.3), artifact signing (285.8.4.3) | ⚠️ Cosign deferred |
| A09: Logging/Monitoring Failures | Audit events, CloudTrail, SIEM (285.8.2.8) | ⚠️ SIEM deferred |
| A10: SSRF | `ssrf_guard.is_safe_url()` on all external requests | ✅ |

## GDPR Art. 32 Compliance

| Requirement | Control | Status |
|-------------|---------|--------|
| Encryption of personal data | KMS + Fernet, TLS 1.3, field-level encryption | ✅ |
| Confidentiality | RLS, tenant isolation, RBAC, ABAC | ✅ |
| Availability | Multi-AZ RDS, K8s HA, backup verification (285.8.3.7) | ⚠️ Backup verify deferred |
| Integrity | Audit tamper evidence, Merkle hash chain | ✅ |
| Resilience | Circuit breaker, retry, Prefect workers | ✅ |
| Regular testing | SAST/DAST/regression, pentest (285.8.1.4) | ⚠️ Pentest deferred |

## Related

- `docs/INCIDENT_RESPONSE.md`
- `docs/runbooks/RB-SEC-001-credential-rotation.md`
- `docs/runbooks/RB-SEC-002-cve-remediation.md`
