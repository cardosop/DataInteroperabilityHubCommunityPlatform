# Prerequisites for Manual Testing

**Version**: 1.0.0  
**Last Updated**: 2026-02-17

---

## 1. Environment Setup (Test Stack)

### 1.1 Start Test Stack

```bash
docker compose -f docker-compose.test.yml up -d
```

**Verify API**:
```bash
curl -s http://localhost:8001/health/
```

**Verify frontend** (includes frontend-test):
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3010/
```

### 1.2 Frontend (Test Stack)

The test stack runs **frontend-test** in Docker (nginx on port 3010). No separate frontend dev server needed.

**Access**:
- Frontend: http://localhost:3010
- Health: http://localhost:3010/health
- OpenAPI JSON: http://localhost:3010/api/v1/openapi.json
- API docs (Swagger): http://localhost:3010/api-docs/

### 1.3 Ensure E2E Test Users Exist

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

**Primary (ManualTest)** — Use these for manual tests:

| Material | Path |
|----------|------|
| ODCS/ODPS contracts | `ManualTest/Front/05-SUPPORT-MATERIAL/contracts/` |
| Sample data files (CSV, JSON) | `ManualTest/Front/05-SUPPORT-MATERIAL/data/` |
| Test users | `ManualTest/Front/05-SUPPORT-MATERIAL/test-users.md` |

**Full index**: [05-SUPPORT-MATERIAL/README.md](05-SUPPORT-MATERIAL/README.md)

**Additional (tests/fixtures)**:

| Material | Path |
|----------|------|
| ODPS sample contracts | `tests/fixtures/odps/v4.1/valid/` |
| ODPS marketplace samples | `tests/fixtures/odps/v4.1/marketplace/` |
| Quality rules | `tests/fixtures/odps/v4.1/with_refs/quality-rules.yaml` |
| Marketplace CKAN | `tests/fixtures/marketplace/ckan/` |

---

## 5. Checklist Before Starting

- [ ] Test stack up: `docker compose -f docker-compose.test.yml ps`
- [ ] API healthy: `curl -s http://localhost:8001/health/`
- [ ] Frontend loads at http://localhost:3010
- [ ] E2E users created (ensure_e2e_user_roles)
- [ ] E2E subscriptions ensured (ensure_e2e_subscription)
- [ ] Browser ready (Chrome/Firefox, DevTools available)

---

## 6. Troubleshooting: Health / OpenAPI Links Not Loading

If http://localhost:3010/health or http://localhost:3010/api/v1/openapi.json does not load:

1. **Ensure frontend-test is running**:
   ```bash
   docker compose -f docker-compose.test.yml ps frontend-test
   ```

2. **Ensure api-service-test is healthy**:
   ```bash
   curl -s http://localhost:8001/health/
   ```

3. **Rebuild frontend if nginx config changed**:
   ```bash
   docker compose -f docker-compose.test.yml up -d --build frontend-test
   ```
