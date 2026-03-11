# Security Test Coverage Matrix

**Last Updated**: 2026-03-08
**Version**: 1.0.0

---

## Overview

This document provides a comprehensive matrix of **service × vulnerability × test file** for the Data Interoperability Hub security test suite. All tests use real implementations (no mocks/stubs except at external boundaries per project policy).

**Related**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md), [RUNBOOKS.md — Security suite](RUNBOOKS.md#security-suite-phase-12a3), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md).

---

## Table of Contents

1. [Vulnerability Categories](#vulnerability-categories)
2. [Service × Vulnerability × Test File Matrix](#service--vulnerability--test-file-matrix)
3. [Test Execution](#test-execution)
4. [CI Integration](#ci-integration)

---

## Vulnerability Categories

| ID | Category | Description |
|----|----------|-------------|
| IDOR | Insecure Direct Object Reference | Cross-tenant access to resources by ID |
| AUTH | Authentication | Unauthenticated access, 401 enforcement |
| INJ | Injection | SQL injection, command injection, path traversal, XSS |
| TENANT | Tenant Isolation | Cross-tenant data leakage, membership validation |
| SECRETS | Secrets & Config | Production secrets, credential exposure |
| HEADERS | Security Headers | CSP, XSS protection, CSRF, forged gateway headers |
| RATE | Rate Limiting | Abuse prevention, rate limit enforcement |
| ODPS | ODPS $ref Security | URL validation, path traversal, SSRF, size/timeout limits |

---

## Service × Vulnerability × Test File Matrix

| Service | Vulnerability | Test File | Notes |
|---------|---------------|-----------|-------|
| **API (general)** | AUTH, HEADERS | `tests/security/test_allowany_public_endpoints.py` | Public endpoints return only public data; no sensitive leakage |
| **API (general)** | HEADERS | `tests/security/test_security_features.py` | CSRF, password hashing, session, JWT, API key, permissions, SQL injection prevention, input validation, security headers |
| **API (general)** | HEADERS | `tests/security/test_security_features_enhanced.py` | CSP, XSS prevention, output encoding, email security, security headers |
| **API (general)** | HEADERS | `tests/security/test_gateway_headers_forged.py` | Forged gateway headers do not override auth; middleware ignores forged headers |
| **API (general)** | SECRETS | `tests/security/test_production_secrets.py` | Production fails on dev default SECRET_KEY/JWT_SECRET_KEY |
| **Auth** | AUTH, TENANT | `tests/security/test_tenant_switch_security.py` | Switch tenant without membership → 403; X-Tenant-Id without membership → 403 |
| **Auth** | AUTH | `tests/security/test_vulnerability_security.py` | Token rotation, PATCH /me cannot set tenant_id/is_platform_admin, SSO redirect validation, login timing |
| **Auth** | TENANT | `tests/security/test_personal_tenant_security.py` | Personal tenant isolation, rate limits, slug collision info not leaked |
| **Users** | TENANT, AUTH | `tests/security/test_admin_user_edit_security.py` | Tenant admin cannot edit other-tenant user; regular user cannot edit any user |
| **Assets** | IDOR | `tests/security/test_idor.py` | Asset, audit retrieve cross-tenant → 403/404 |
| **Assets** | IDOR | `tests/security/test_data_first_asset_idor.py` | Data-first cross-tenant file_id → 403/404 |
| **Contracts** | AUTH, IDOR | `tests/security/test_datacontract_security.py` | Contracts list/create/retrieve unauthenticated → 401; cross-tenant retrieve → 403/404 |
| **Contracts** | IDOR | `tests/security/test_idor_contracts.py` | Contract retrieve cross-tenant → 403/404 |
| **Contracts (ODPS)** | ODPS | `hub/apps/contracts/tests/security/test_ref_resolver_security.py` | URL validation, path traversal, rate limiting, size/timeout, audit |
| **Contracts (ODPS)** | ODPS | `tests/security/penetration_test_odps_ref_resolver.py` | Path traversal, URL injection (SSRF/XSS), rate/size bypass attempts |
| **Datasets** | IDOR | `tests/security/test_idor_datasets.py` | Dataset retrieve cross-tenant; list asset_id filter tenant isolation |
| **Data Quality** | AUTH, IDOR | `tests/security/test_dq_security.py` | DQ runs list/retrieve unauthenticated → 401; tenant isolation |
| **Data Quality** | IDOR | `tests/security/test_idor_dq.py` | DQ run retrieve cross-tenant → 403/404 |
| **Compliance** | AUTH, IDOR | `tests/security/test_compliance_security.py` | Compliance runs list/retrieve unauthenticated → 401; tenant isolation |
| **Compliance** | IDOR | `tests/security/test_idor_compliance.py` | Compliance run retrieve cross-tenant → 403/404 |
| **Governance** | IDOR | `tests/security/test_idor_governance.py` | Access request retrieve cross-tenant → 403/404 |
| **Webhooks** | AUTH, IDOR | `tests/security/test_webhook_security.py` | Webhooks list/retrieve unauthenticated → 401; tenant isolation |
| **Webhooks** | IDOR | `tests/security/test_idor_webhooks.py` | Webhook retrieve cross-tenant → 403/404 |
| **Scheduled Ingestion/Export** | IDOR | `tests/security/test_idor_scheduled.py` | Scheduled ingestion/export retrieve cross-tenant → 403/404 |
| **Jobs** | IDOR | `tests/security/test_idor_jobs.py` | Job retrieve cross-tenant → 403/404 |
| **Marketplace** | IDOR | `tests/security/test_idor_marketplace.py` | Listing retrieve cross-tenant → 403/404 |
| **Marketplace** | INJ, TENANT, SECRETS, RATE | `tests/security/test_marketplace_security.py` | Connector auth, tenant isolation, SQL/XSS/path/command injection, credential encryption, rate limiting |
| **Search** | AUTH, TENANT | `tests/security/test_search_security.py` | Search unauthenticated → 401; tenant isolation |
| **Search** | INJ | `tests/security/test_injection_search.py` | SQL-like query/type/tags params |
| **Virtualization** | INJ | `tests/security/test_injection_virtualization.py` | Virtual datasets list SQL-like search/ordering/status |
| **Files** | AUTH, INJ, TENANT | `tests/security/test_files_security.py` | Unauthenticated list → 401; path traversal, disallowed file type, tenant isolation |
| **Health** | AUTH, HEADERS | `tests/security/test_health_security.py` | Liveness/health unauthenticated OK; no sensitive data in response |
| **Versioning** | AUTH, IDOR | `tests/security/test_versioning_security.py` | Versioning list/retrieve/compare unauthenticated → 401; cross-tenant → 404 |
| **AI** | AUTH, TENANT | `tests/security/test_ai_security.py` | Natural language search, schema matching unauthenticated → 401; tenant isolation |
| **ML** | AUTH, IDOR | `tests/security/test_ml_security.py` | ML models list unauthenticated → 401; retrieve cross-tenant → 404 |
| **Data Mesh** | AUTH, IDOR | `tests/security/test_data_mesh_security.py` | Mesh domains list unauthenticated → 401; retrieve cross-tenant → 404 |
| **Social** | AUTH, IDOR | `tests/security/test_social_security.py` | Ratings/communities unauthenticated → 401; rating cross-tenant → 403/404 |
| **Phase 25 (SaaS)** | TENANT, AUTH, SECRETS | `tests/security/test_phase25_security.py` | Billing tenant isolation, tenant suspend/usage PA-only, erasure user-only, Stripe webhook signature, worker API key/tenant isolation |
| **Audit, Assets, etc.** | INJ | `tests/security/test_injection.py` | Audit/contracts/assets/datasets/marketplace SQL-like params; health command injection |
| **Cross-tenant** | IDOR | `tests/security/test_security_fixtures.py` | two_tenant_setup cross-tenant IDOR validation |

---

## Test Execution

### Full Security Suite

```bash
# Run tests/security/ (pytest)
pytest tests/security/ -v --tb=short --junit-xml=security-test-results.xml

# Run ODPS ref resolver security (Django test)
cd hub && python manage.py test hub.apps.contracts.tests.security.test_ref_resolver_security --verbosity=2 --failfast

# Run ODPS ref resolver penetration tests
cd hub && python manage.py test tests.security.penetration_test_odps_ref_resolver --verbosity=2 --failfast
```

**Target duration**: <10 minutes for full security suite (tests/security/ + ODPS ref resolver + penetration).

**Validation script**: `./scripts/run_validation_29_7.sh --security` runs the full security suite (tests/security/ + ODPS ref resolver + penetration) and asserts <10 min.

### Via Phase 12A Script

```bash
./scripts/run_phase_12a_full_suites.sh
```

Security runs as Phase 12A.3.1; artifacts under `test_reports_comprehensive/{date}/security/`.

---

## CI Integration

| CI Job | Command | Artifacts |
|--------|---------|-----------|
| `test-security` | `pytest tests/security/ -v --tb=short --junit-xml=security-test-results.xml` | `security-test-results-suite-{run_id}` (JUnit XML) |
| `test-odps-ref-resolver-security` | `python manage.py test hub.apps.contracts.tests.security.test_ref_resolver_security` + `tests.security.penetration_test_odps_ref_resolver` | `security-test-results-{run_id}` (JUnit XML) |
| `test` (main) | Includes ODPS ref resolver + penetration in backend phase | `test-results-{run_id}-py{version}` (includes e2e, unit, integration) |

**Artifact retention**: 30 days.

---

## Maintenance

Update this matrix when:
1. New security tests are added
2. New services or vulnerability categories are introduced
3. Test files are renamed or reorganized

**Update frequency**: After each security-related change or phase completion.
