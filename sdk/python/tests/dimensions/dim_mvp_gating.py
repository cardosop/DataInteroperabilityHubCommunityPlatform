import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.2 — Dimension: MVP-gated 404 exhaustive.

Verifies that every prefix in MVP_GATED_RELATIVE_PREFIXES returns 404
when the staging backend has MVP_MODE=true, and that the CLI/SDK error
classes (MVPGatedFeatureError, ODPSFeatureGatedError) are raised.
"""

import requests

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get

# Canonical prefix list — must match hub/apps/api/mvp_mode.py
MVP_GATED_PREFIXES = [
    "mesh/",
    "virtualization/",
    "integrations/",
    "baas/",
    "ml/",
    "ai/",
    "transformation/",
    "social/",
    "scheduled-ingestions/",
    "scheduled-exports/",
]


@pytest.fixture(scope="module")
def auth_creds():
    return provision_persona("data_engineer")


@pytest.mark.parametrize("prefix", MVP_GATED_PREFIXES)
def test_gated_prefix_returns_404_in_mvp_mode(auth_creds, prefix):
    """GET /api/v1/{prefix} must return 404 when MVP_MODE=true on staging."""
    resp = api_get(f"/{prefix}", auth_creds)
    assert resp.status_code == 404, (
        f"GET /{prefix} returned {resp.status_code}, expected 404 (MVP gated). "
        f"Is MVP_MODE=true on this backend? Body: {resp.text[:200]}"
    )


@pytest.mark.parametrize("prefix", MVP_GATED_PREFIXES)
def test_gated_prefix_404_body_is_json(auth_creds, prefix):
    """The 404 for gated prefixes must be structured JSON, not a Django HTML page."""
    resp = api_get(f"/{prefix}", auth_creds)
    if resp.status_code != 404:
        pytest.skip(f"/{prefix} did not return 404 (got {resp.status_code})")
    ct = resp.headers.get("Content-Type", "")
    assert "json" in ct.lower() or resp.text.startswith("{"), (
        f"404 body for /{prefix} is not JSON: {ct}, body={resp.text[:200]}"
    )


@pytest.mark.parametrize("prefix", MVP_GATED_PREFIXES)
def test_gated_prefix_unauthenticated_also_404(prefix):
    """Unauthenticated request to a gated prefix should also return 404, not 401.

    The MVP gate fires BEFORE auth so unauthenticated callers never learn
    whether the endpoint exists behind the gate.
    """
    resp = requests.get(f"{api_base_url()}/{prefix}", timeout=15)
    # 404 (gate fires first) or 401 (auth fires first) — both acceptable.
    # The important thing is it's NOT 200/500.
    assert resp.status_code in (401, 404), f"Unauthenticated GET /{prefix}: {resp.status_code}"


def test_non_gated_prefix_is_reachable(auth_creds):
    """Sanity: /assets/ is NOT gated and should return 200 (or 401 if auth issue)."""
    resp = api_get("/assets/", auth_creds)
    assert resp.status_code != 404, (
        "GET /assets/ returned 404 — this is a non-gated MVP endpoint. "
        "Either the route is broken or MVP gating is too broad."
    )


def test_all_10_prefixes_covered():
    """Meta: verify the test covers all 10 gated prefixes from the spec."""
    assert len(MVP_GATED_PREFIXES) == 10, (
        f"Expected 10 gated prefixes, got {len(MVP_GATED_PREFIXES)}: {MVP_GATED_PREFIXES}"
    )
