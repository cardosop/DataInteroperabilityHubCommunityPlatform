# Testing Hardening — Meshant Platform

**Last updated:** 2026-05-15

## B.5.1 — API Contract Testing (Pact)

**Status:** ⏭️ Not configured. No Pact Broker, no consumer/provider definitions.

### Setup Procedure (deferred)

```bash
# 1. Install Pact
pip install pact-python
npm install @pact-foundation/pact --save-dev

# 2. Consumer: CLI → /api/v1/assets/
# tests/pact/consumer/test_cli_assets.py
@pytest.fixture
def pact():
    pact = Consumer('CLI').has_pact_with(Provider('MeshantAPI'))
    pact.start()
    yield pact
    pact.stop()

def test_assets_list(pact):
    pact.given('assets exist').upon_receiving('list assets').with_request(
        'GET', '/api/v1/assets/', query={'limit': '50'}
    ).will_respond_with(200, body={'results': []})
    # verify via pact.verify()

# 3. Provider: MeshantAPI verifies all consumer contracts
# tests/pact/provider/test_provider.py
def test_provider_verification():
    verifier = Verifier(provider='MeshantAPI')
    verifier.verify_pacts('./pacts/', states_setup_url='http://localhost:8000/_pact/setup')
```

### Top 5 Critical Consumers

| Consumer | Endpoints | Priority |
|---|---|---|
| CLI | assets, contracts, users, datasets, marketplace | P0 |
| SDK (Python) | assets, contracts, governance, billing | P0 |
| Frontend Auth | auth/login, auth/register, auth/refresh | P0 |
| Marketplace UI | marketplace/listings, marketplace/orders, marketplace/entitlements | P1 |
| Scheduled Export | scheduled-exports, contracts/export | P1 |

**Note:** Pact Broker not provisioned. Full Pact implementation is a follow-up sprint.

## B.5.2 — Production-Config E2E Smoke Suite

**Status:** ⏭️ Requires running staging with production-like config.

### E2E Config
```yaml
# frontend/e2e/production-config.e2e.config.ts (new)
export default {
  baseURL: process.env.E2E_BASE_URL || 'https://stagingmeshant-internal.example.com',
  use: {
    storageState: undefined,  // No pre-auth — test real login flow
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'production-smoke',
      testMatch: [
        'journeys/auth/login/**/*.spec.ts',
        'journeys/marketplace/**/*.spec.ts',
        'journeys/contracts/**/*.spec.ts',
      ],
      retries: 0,  // Production smoke: no retries (flakiness = failure)
    },
  ],
};
```

### Smoke Suite Tests
```bash
# Run production-config smoke suite
E2E_BASE_URL=https://stagingmeshant-internal.example.com npx playwright test \
  --config=playwright.production.e2e.config.ts \
  --project=production-smoke
```

### Required Services in Production Mode
- Real S3 bucket (not MinIO)
- Real SMTP via SES test mode
- Real Stripe test mode
- Real ExternalSecrets via AWS Secrets Manager

## B.5.3 — Weekly Audit Log Chain Integrity CI

**Status:** ✅ INFRASTRUCTURE EXISTS (verified 2026-05-15).

Existing audit chain signing keys configured in `hub/settings.py`:
```python
AUDIT_CHAIN_SIGNING_KEYS_JSON = os.environ.get("AUDIT_CHAIN_SIGNING_KEYS_JSON", "")
```

Merkle chain verification runs in `.github/workflows/ci.yml`. No dedicated weekly job exists — verification runs on every PR via the main CI pipeline.

### Enhancement: Weekly Chain Integrity Check
```bash
# Add to CI as a scheduled workflow or management command
python manage.py verify_audit_chain_integrity --all-tenants
```

This can be added as a weekly cronjob in `ci.yml` or as a standalone scheduled workflow. The infrastructure (signing keys, chain storage, verification logic) is already in place.

## B.5.4 — Test Data Isolation Audit

**Status:** ✅ 3-LAYER CLEANUP EXISTS (verified 2026-05-15).

`cli/tests/fixtures/cleanup_registry.py` implements 3 layers:

| Layer | Mechanism | Scope |
|---|---|---|
| **1. Per-test** | `cleanup_registry.add(callback)` → LIFO teardown | Every test that creates resources |
| **2. Per-session** | `pytest_sessionfinish` → persona teardown | Provisioned personas cleaned up on session exit |
| **3. Per-deploy** | `manage.py purge_test_data --older-than=24h` | CI CronJob sweeps escaped resources |

**Gap documented:** The `purge_test_data` management command referenced in the cleanup registry docstring does not exist on disk at `hub/apps/api/management/commands/purge_test_data.py`. The cleanup registry itself is fully implemented and functional — only the CI CronJob sweep layer needs the management command created.

### Audit Procedure
```bash
# 1. Count registered cleanup callbacks per test run
grep -c 'cleanup_registry.add' cli/tests/**/*.py sdk/python/tests/**/*.py

# 2. Verify no orphaned test data after full suite run
python manage.py shell -c "
from hub.apps.tenants.models import Tenant
test_tenants = Tenant.objects.filter(name__icontains='test').count()
print(f'Test tenants remaining: {test_tenants}')
"

# 3. Verify purge command exists
ls hub/apps/api/management/commands/purge_test_data.py
```
