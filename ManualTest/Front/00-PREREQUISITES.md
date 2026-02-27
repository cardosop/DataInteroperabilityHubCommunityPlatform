# Prerequisites for Manual Testing

**Version**: 1.0.0  
**Last Updated**: 2026-02-17

---

## 1. Environment Setup

### 1.1 Backend (API)

The backend must be running. Use one of:

```bash
# Option A: Test stack (API on 8001) — recommended for manual QA
docker compose -f docker-compose.test.yml up -d

# Option B: Dev stack (API on 8000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Verify**:
```bash
curl -s http://localhost:8001/health/   # Test stack
# or
curl -s http://localhost:8000/health/   # Dev stack
```

### 1.2 Frontend

```bash
cd frontend

# Set proxy to match backend
export VITE_PROXY_TARGET=http://localhost:8001   # Test stack
# or
export VITE_PROXY_TARGET=http://localhost:8000   # Dev stack

npm run dev
```

**Verify**: Open http://localhost:5173 in a browser.

### 1.3 Ensure E2E Test Users Exist

When using the test stack (port 8001):

```bash
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles
docker exec hub-test-api python hub/manage.py ensure_e2e_subscription
```

---

## 2. Test User Credentials

All test users use password: **TestPass123**

| Persona | Email | Roles |
|---------|-------|-------|
| Data Product Owner | e2e_test@example.com | DATA_PROVIDER |
| Data Consumer | e2e_consumer@example.com | DATA_CONSUMER |
| Tenant Admin | e2e_admin@example.com | TENANT_ADMIN, DATA_PROVIDER |
| Platform Admin | e2e_platform@example.com | Platform Admin |
| Auditor | e2e_auditor@example.com | AUDITOR |
| Compliance Officer | e2e_cpo@example.com | TENANT_ADMIN, DATA_PROVIDER, COMPLIANCE_OFFICER |
| External Developer | e2e_developer@example.com | DATA_PROVIDER |
| Data Mesh Domain Owner | e2e_dmo@example.com | TENANT_ADMIN, DATA_PROVIDER |

Full credentials matrix: [05-SUPPORT-MATERIAL/test-users.md](05-SUPPORT-MATERIAL/test-users.md)

---

## 3. Browser Requirements

- **Chrome** or **Firefox** (latest)
- Clear cookies/localStorage before auth tests if switching users
- DevTools open (F12) for network/console inspection

---

## 4. Support Material Locations

| Material | Path |
|----------|------|
| ODPS sample contracts | `tests/fixtures/odps/v4.1/valid/` |
| ODPS marketplace samples | `tests/fixtures/odps/v4.1/marketplace/` |
| Contract YAML | `tests/fixtures/odps/v2.x/with_refs/contract-definition.yaml` |
| Quality rules | `tests/fixtures/odps/v4.1/with_refs/quality-rules.yaml` |
| Marketplace CKAN | `tests/fixtures/marketplace/ckan/` |

---

## 5. Checklist Before Starting

- [ ] Backend healthy (health endpoint returns 200)
- [ ] Frontend loads at http://localhost:5173
- [ ] VITE_PROXY_TARGET matches backend port
- [ ] E2E users created (ensure_e2e_user_roles)
- [ ] E2E subscriptions ensured (ensure_e2e_subscription)
- [ ] Browser ready (Chrome/Firefox, DevTools available)
