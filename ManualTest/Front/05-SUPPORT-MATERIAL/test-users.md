# Test User Credentials Matrix

**Version**: 1.0.0  
**Last Updated**: 2026-02-17  
**Source**: `frontend/e2e/setup/create-test-user.ts`, `hub/apps/users/management/commands/ensure_e2e_user_roles.py`

---

## Password

All test users use: **TestPass123**

(Password must contain uppercase, lowercase, and number.)

---

## Credentials by Persona

| Persona | Email | Password | Roles |
|---------|-------|----------|-------|
| Data Product Owner | e2e_test@example.com | TestPass123 | DATA_PROVIDER |
| Data Consumer | e2e_consumer@example.com | TestPass123 | DATA_CONSUMER |
| Tenant Admin | e2e_admin@example.com | TestPass123 | TENANT_ADMIN, DATA_PROVIDER |
| Platform Admin | e2e_platform@example.com | TestPass123 | Platform Admin (is_platform_admin=True) |
| Auditor | e2e_auditor@example.com | TestPass123 | AUDITOR |
| Compliance Officer | e2e_cpo@example.com | TestPass123 | TENANT_ADMIN, DATA_PROVIDER, COMPLIANCE_OFFICER |
| External Developer | e2e_developer@example.com | TestPass123 | DATA_PROVIDER |
| Data Mesh Domain Owner | e2e_dmo@example.com | TestPass123 | TENANT_ADMIN, DATA_PROVIDER |

---

## Setup Commands

When using the test stack (API on 8001):

```bash
# Create/ensure all E2E persona users
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles

# Ensure E2E tenants have active subscription (for asset create, publish, etc.)
# Note: Covers e2e_test, e2e_consumer, e2e_admin, e2e_platform, e2e_auditor, e2e_cpo.
# e2e_developer and e2e_dmo are not included; they may hit 403 for asset creation.
docker exec hub-test-api python hub/manage.py ensure_e2e_subscription
```

---

## Visitor / Unauthenticated

For auth journeys (register, login, password reset), use a **new email** for registration tests, or the credentials above for login tests.
