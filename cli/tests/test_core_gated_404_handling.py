"""
P.5 — core-mode CLI gating pass (Phase 313.4 counterpart of
``test_mvp_gated_404_handling.py``).

Tests construct real :class:`requests.Response` objects (no mocking beyond
the response's own setters) and exercise the real ``handle_api_error``.
Every PAID CLI group MUST surface ``CoreFeatureUnavailableError`` when the
core-only backend 404s its paid path; core paths MUST NOT be intercepted.

Per the precedent's rendering rule, exactly ONE test asserts the fully
rendered message; every other test asserts structural fields only.
"""

from __future__ import annotations

from datahub_cli.odps_errors import (
    CoreFeatureUnavailableError,
    ODPSCLIError,
    handle_api_error,
)

STAGING_BASE = "https://meshant-internal.example.com"


# Prefix → expected feature/group.  One representative path per group;
# the full prefix table is covered separately by the drift test.
_GROUP_REPRESENTATIVE = {
    "marketplace": "api/v1/marketplace/listings/",
    "billing": "api/v1/billing/subscription/",
    "baas": "api/v1/baas/tenants/",
    "ml": "api/v1/ml/models/",
    "social": "api/v1/social/ratings/",
    "semantic": "api/v1/semantic/map/",
    "graphql": "graphql/",
}


def test_every_paid_group_returns_core_feature_unavailable():
    """Every paid CLI group must gate against a core backend."""
    for group, path in _GROUP_REPRESENTATIVE.items():
        err = handle_api_error(
            response_text="Not Found.",
            status_code=404,
            endpoint=path,
            request_url=f"{STAGING_BASE}/{path}",
        )
        assert isinstance(err, CoreFeatureUnavailableError), (
            f"group {group!r}: expected CoreFeatureUnavailableError, got {type(err).__name__}"
        )
        assert err.code == "SAAS_FEATURE_UNAVAILABLE"
        assert err.feature == group


def test_nested_paid_path_gates_as_marketplace():
    """P.5 D3 — the nested integrations/marketplace path is gated."""
    err = handle_api_error(
        response_text="Not Found.",
        status_code=404,
        endpoint="api/v1/integrations/marketplace/connections/",
        request_url=f"{STAGING_BASE}/api/v1/integrations/marketplace/connections/",
    )
    assert isinstance(err, CoreFeatureUnavailableError)
    assert err.feature == "marketplace"
    assert err.code == "SAAS_FEATURE_UNAVAILABLE"


def test_core_paths_are_not_intercepted():
    """Core-owned paths must fall through to the generic error path."""
    for path in ("api/v1/assets/", "api/v1/integrations/health/", "api/v1/developer/plugins/"):
        err = handle_api_error(
            response_text="Not Found.",
            status_code=404,
            endpoint=path,
            request_url=f"{STAGING_BASE}/{path}",
        )
        assert not isinstance(err, CoreFeatureUnavailableError), f"core path {path!r} must not gate"
        assert isinstance(err, ODPSCLIError)  # still a typed CLI error


def test_non_404_status_is_not_intercepted():
    """The gate only fires on 404 (the core backend's paid-path shape)."""
    err = handle_api_error(
        response_text="Server Error",
        status_code=500,
        endpoint="api/v1/marketplace/listings/",
        request_url=f"{STAGING_BASE}/api/v1/marketplace/listings/",
    )
    assert not isinstance(err, CoreFeatureUnavailableError)


def test_rendered_message_carries_feature_and_endpoint():
    """The ONE full-message assertion (precedent rule)."""
    err = handle_api_error(
        response_text="Not Found.",
        status_code=404,
        endpoint="api/v1/marketplace/listings/",
        request_url=f"{STAGING_BASE}/api/v1/marketplace/listings/",
    )
    rendered = str(err)
    assert "marketplace" in rendered
    assert "SaaS feature" in rendered
    assert "not available in this deployment" in rendered
    assert "api/v1/marketplace/listings/" in rendered
