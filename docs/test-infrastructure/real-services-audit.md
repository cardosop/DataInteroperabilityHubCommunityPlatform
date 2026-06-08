# Real Services Only — Mock Audit

> Phase 312.11.3 — Audits `unittest.mock.patch`, `responses`, and `moto`
> usage in conftest fixtures. Documents justifications or replacements.

## Audit scope

All conftest files across the repository plus key test infrastructure files.

## Findings

### 1. `cli/tests/conftest.py` — `unittest.mock` imports

**File:** `cli/tests/conftest.py:9`
```python
from unittest.mock import Mock, patch, MagicMock
```

**Usage:** Two fixtures use mocks:
- `mock_api_client` — creates a mock API client for unit tests
- `mock_auth_manager` — creates a mock auth manager for auth tests

**Justification:** These are at an EXTERNAL BOUNDARY. CLI unit tests exercise
command logic, not the HTTP transport. The `mock_api_client` fixture replaces
the HTTP client with a mock so unit tests don't make real network calls. This
is the correct pattern — unit tests should NOT require a running API.

**Status:** ✅ JUSTIFIED — external boundary mock. No replacement needed.

### 2. `tests/conftest.py` — service fixtures (Phase 312.3)

**Previously:** `disable_semantic_service_in_tests` was an `autouse=True`
fixture that silently mocked `hub.apps.semantic.utils` functions.

**Fixed in Phase 312.3.7:** Replaced with `semantic_service` fixture using
the health-check + skip pattern:
```python
@pytest.fixture(scope="session")
def semantic_service():
    if not wait_for_service_health(f"{service_url}/health", timeout=30):
        pytest.skip(f"Semantic service not available at {service_url}")
    return service_url
```

**Status:** ✅ FIXED — no remaining silent autouse mocks.

### 3. `hub/conftest.py` — no mocks

**File:** `hub/conftest.py`
**Mock count:** 0

**Status:** ✅ CLEAN

### 4. SDK conftest — no mocks

**Files:** `sdk/python/tests/conftest.py`, various subdirectory conftests
**Mock count:** 0

**Status:** ✅ CLEAN — uses health-check + skip pattern for service dependencies.

### 5. Service-level conftests

**Files:** `services/*/tests/conftest.py`
Each service conftest uses the health-check pattern:
```python
@pytest.fixture(scope="session")
def service_url():
    url = os.getenv("SERVICE_URL", "http://localhost:<port>")
    if not check_health(url):
        pytest.skip("Service not available")
    return url
```

**Status:** ✅ CLEAN — consistent health-check pattern.

### 6. Existing mock patterns in test files (not conftests)

Several integration test files use `responses` library or `moto` for AWS
service mocking. These are at the external service boundary:

- `tests/integration/test_aws_*` — moto S3 mocking (external AWS boundary)
- `tests/integration/test_stripe_*` — responses mocking (external Stripe boundary)

**Justification:** AWS and Stripe are external SaaS services. Mocking them
in integration tests is the standard industry practice. Real AWS/Stripe
calls require credentials and incur costs.

**Status:** ✅ JUSTIFIED — external SaaS boundaries.

## Summary

| File | Mock Type | Count | Status |
|---|---|---|---|
| `cli/tests/conftest.py` | `unittest.mock` imports | 1 (import line) | ✅ Justified (unit test external boundary) |
| `tests/conftest.py` | autouse mock | 0 (removed in 312.3) | ✅ Fixed |
| `hub/conftest.py` | any mock | 0 | ✅ Clean |
| `sdk/python/tests/conftest.py` | any mock | 0 | ✅ Clean |
| Service conftests | any mock | 0 | ✅ Clean |
| AWS integration tests | `moto` | ~5 files | ✅ Justified (AWS external boundary) |
| Stripe integration tests | `responses` | ~3 files | ✅ Justified (Stripe external boundary) |

## Enforcement

New mocks in conftest files are blocked by code review. The `check_marker_consistency.py`
script does not scan for mocks (that's a separate concern). Mocks at external
boundaries are allowed with documented justification.
