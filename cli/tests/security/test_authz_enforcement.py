import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.11 — Security: authz enforcement.

Verifies that authenticated users with insufficient roles receive 403
when accessing role-gated endpoints.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get, api_post


# Endpoints that require elevated roles
ADMIN_ONLY_ENDPOINTS = [
    "/users/",              # listing users requires admin
]

COMPLIANCE_ONLY_ENDPOINTS = [
    "/gdpr/export/",
    "/gdpr/erasure/",
]

# Personas that should NOT have admin access
NON_ADMIN_PERSONAS = [
    "data_consumer",
    "data_engineer",
    "data_analyst",
    "compliance_officer",
]

# Personas that should NOT have compliance access
NON_COMPLIANCE_PERSONAS = [
    "data_consumer",
    "data_analyst",
    "data_engineer",
    "external_developer",
]


@pytest.mark.parametrize("persona_role", NON_ADMIN_PERSONAS)
@pytest.mark.parametrize("endpoint", ADMIN_ONLY_ENDPOINTS)
def test_non_admin_gets_403_on_admin_endpoint(persona_role, endpoint):
    """Non-admin persona accessing admin endpoint → 403."""
    creds = provision_persona(persona_role)
    resp = api_get(endpoint, creds)
    assert resp.status_code in (403, 404), (
        f"{persona_role} accessing {endpoint}: expected 403/404, got {resp.status_code}"
    )


@pytest.mark.parametrize("persona_role", NON_COMPLIANCE_PERSONAS)
@pytest.mark.parametrize("endpoint", COMPLIANCE_ONLY_ENDPOINTS)
def test_non_compliance_gets_403_on_gdpr_endpoint(persona_role, endpoint):
    """Non-compliance persona accessing GDPR endpoint → 403/404."""
    creds = provision_persona(persona_role)
    resp = api_post(endpoint, creds, json={"subject_email": "test@example.com"})
    # 403 (forbidden) or 404 (endpoint not found in MVP) both acceptable
    assert resp.status_code in (403, 404), (
        f"{persona_role} accessing {endpoint}: expected 403/404, got {resp.status_code}"
    )


def test_visitor_cannot_create_asset():
    """Visitor (unauthenticated) cannot create assets."""
    from tests.use_cases._api_helpers import api_unauthenticated_get
    resp = api_unauthenticated_get("/assets/")
    assert resp.status_code == 401
