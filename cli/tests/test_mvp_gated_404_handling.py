"""
End-to-end tests for the CLI MVP-gated 404 error path.

These tests construct real :class:`requests.Response` objects (no mocking
library beyond the response's own setters) and exercise the real
``handle_api_error`` function. Per the spec, **exactly one** test asserts the
fully rendered message string for one representative gated feature; every
other test asserts only the structural fields (``code``, ``feature``,
``prefix``, ``endpoint``, ``environment_url``).

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

import pytest
import requests
from datahub_cli._mvp_gates import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_RELATIVE_PREFIXES,
)
from datahub_cli.odps_errors import (
    ODPSCLIError,
    ODPSFeatureGatedError,
    handle_api_error,
)

STAGING_BASE = "https://meshant-internal.example.com"


def _build_404(url: str) -> requests.Response:
    """Construct a real ``requests.Response`` representing a 404 from ``url``."""
    response = requests.Response()
    response.status_code = 404
    response.url = url  # type: ignore[assignment]
    response._content = b'{"detail":"Not Found."}'
    response.headers["Content-Type"] = "application/json"
    return response


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_RELATIVE_PREFIXES))
def test_404_against_every_gated_prefix_raises_feature_gated_error(prefix: str) -> None:
    """Each gated prefix MUST yield ``ODPSFeatureGatedError`` with correct fields."""
    full_url = f"{STAGING_BASE}/api/v1/{prefix}list"
    response = _build_404(full_url)
    err = handle_api_error(
        response.text,
        response.status_code,
        endpoint=prefix + "list",
        request_url=full_url,
    )
    assert isinstance(err, ODPSFeatureGatedError)
    # Backwards-compat contract: still catchable as ODPSCLIError.
    assert isinstance(err, ODPSCLIError)
    # Structural assertions only — no full-message comparison here.
    assert err.code == MVP_FEATURE_GATED_CODE
    assert err.error_code == MVP_FEATURE_GATED_CODE
    assert err.prefix == prefix
    assert err.feature == MVP_GATED_FEATURE_NAMES[prefix]
    assert err.endpoint == prefix + "list"
    assert err.environment_url == STAGING_BASE


def test_existing_except_odpsclierror_still_catches_gated_404() -> None:
    """Refining ``except ODPSCLIError`` to ``ODPSFeatureGatedError`` MUST be additive."""
    full_url = f"{STAGING_BASE}/api/v1/mesh/clusters"
    err = handle_api_error("", 404, endpoint="mesh/clusters", request_url=full_url)
    caught: ODPSCLIError | None = None
    try:
        raise err
    except ODPSCLIError as e:  # pragma: no branch — single path
        caught = e
    assert caught is err
    assert isinstance(caught, ODPSFeatureGatedError)


def test_404_against_non_gated_endpoint_returns_generic_error() -> None:
    """A 404 on a non-gated route MUST NOT be misclassified as MVP-gated."""
    full_url = f"{STAGING_BASE}/api/v1/contracts/does-not-exist"
    err = handle_api_error("", 404, endpoint="contracts/does-not-exist", request_url=full_url)
    assert not isinstance(err, ODPSFeatureGatedError)
    assert err.error_code != MVP_FEATURE_GATED_CODE


def test_non_404_status_against_gated_path_is_not_misclassified() -> None:
    """A 500 against a gated path MUST NOT be turned into a feature-gated error."""
    full_url = f"{STAGING_BASE}/api/v1/mesh/clusters"
    err = handle_api_error('{"error":"boom"}', 500, endpoint="mesh/clusters", request_url=full_url)
    assert not isinstance(err, ODPSFeatureGatedError)


def test_handle_api_error_works_without_request_url() -> None:
    """``request_url`` is optional; detection still works from ``endpoint`` alone."""
    err = handle_api_error("", 404, endpoint="ml/jobs")
    assert isinstance(err, ODPSFeatureGatedError)
    assert err.prefix == "ml/"
    # No request_url given → environment_url falls back to empty string.
    assert err.environment_url == ""


def test_full_rendered_message_for_one_representative_feature() -> None:
    """The exactly-one full-message regression lock for the Data Mesh feature."""
    full_url = f"{STAGING_BASE}/api/v1/mesh/clusters/abc"
    err = handle_api_error("", 404, endpoint="mesh/clusters/abc", request_url=full_url)
    assert isinstance(err, ODPSFeatureGatedError)
    expected = (
        "The 'Data Mesh' feature is not available in the current MVP release.\n"
        "\n"
        "  Endpoint:    mesh/clusters/abc\n"
        "  Environment: https://meshant-internal.example.com\n"
        "  Status:      Post-MVP (planned)\n"
        "\n"
        "This is a deliberate gate, not a missing resource — the route exists in\n"
        "the codebase and will be enabled after the MVP release. To track when\n"
        "'Data Mesh' becomes available, see the project roadmap.\n"
        "\n"
        "Error code: MVP_FEATURE_GATED"
    )
    assert err.message == expected


def test_format_message_includes_suggestion() -> None:
    """The Click rendering path (``format_message``) includes the suggestion line."""
    err = handle_api_error(
        "", 404, endpoint="baas/auth", request_url=f"{STAGING_BASE}/api/v1/baas/auth"
    )
    assert isinstance(err, ODPSFeatureGatedError)
    rendered = err.format_message()
    assert "Suggestion" in rendered
    assert "Backend-as-a-Service" in rendered
