"""
Phase 250.0.14 / D250.15 — tests for cross-service version-compatibility
startup check.

TDD doctrine:
* No mocks of business logic — only HTTP transport is stubbed (httpx
  responses) because real microservices are out-of-process.
* Every behaviour clause from D250.15 has at least one test:
  - Service version >= required → no error.
  - Service version < required → ImproperlyConfigured (production).
  - Service unreachable → ImproperlyConfigured (production).
  - Non-production → degrade to warning, no raise.
  - Master switch off → skip silently.
  - Malformed response → ImproperlyConfigured.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from hub.apps.core.cross_service_version_check import (
    _compare_semver,
    _parse_semver,
    run_cross_service_version_check,
)


# ---------------------------------------------------------------------------
# Pure-function unit tests — semver parsing & comparison
# ---------------------------------------------------------------------------


class TestParseSemver:
    def test_parses_valid_version(self):
        assert _parse_semver("1.2.3") == (1, 2, 3)

    def test_parses_version_with_prerelease_suffix(self):
        # The patch position keeps only the leading integer; suffixes
        # are tolerated per the docstring contract.
        assert _parse_semver("1.2.3-rc.1") == (1, 2, 3)
        assert _parse_semver("1.2.3+build.42") == (1, 2, 3)

    def test_parses_version_with_zero_components(self):
        assert _parse_semver("0.0.0") == (0, 0, 0)

    def test_rejects_two_part_version(self):
        with pytest.raises(ImproperlyConfigured, match="Invalid semver"):
            _parse_semver("1.2")

    def test_rejects_non_numeric(self):
        with pytest.raises(ImproperlyConfigured, match="Invalid semver"):
            _parse_semver("v1.2.3")

    def test_rejects_empty_string(self):
        with pytest.raises(ImproperlyConfigured, match="Invalid semver"):
            _parse_semver("")


class TestCompareSemver:
    def test_equal_versions(self):
        assert _compare_semver("1.2.3", "1.2.3") == 0

    def test_actual_greater_than_required(self):
        assert _compare_semver("1.2.4", "1.2.3") == 1
        assert _compare_semver("2.0.0", "1.99.99") == 1

    def test_actual_less_than_required(self):
        assert _compare_semver("1.2.3", "1.2.4") == -1
        assert _compare_semver("0.9.0", "1.0.0") == -1

    def test_compares_minor_before_patch(self):
        # 1.10.0 > 1.9.99 — numeric comparison, not lexicographic.
        assert _compare_semver("1.10.0", "1.9.99") == 1


# ---------------------------------------------------------------------------
# Integration tests — full check with mocked httpx transport
# ---------------------------------------------------------------------------


def _stub_httpx_response(status_code: int, json_body: dict | None = None):
    """Return a real ``httpx.Response`` so the test exercises the real
    HTTPX response API (``.json()``, ``.status_code``) — only the
    transport is stubbed."""
    if json_body is None:
        return httpx.Response(status_code=status_code, content=b"")
    import json as _json
    return httpx.Response(
        status_code=status_code,
        content=_json.dumps(json_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


class TestVersionCheckProduction:
    """Production environment — every failure mode raises."""

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="1.0.0",
    )
    def test_passes_when_both_services_meet_requirements(self):
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = [
                _stub_httpx_response(200, {"version": "1.2.3"}),
                _stub_httpx_response(200, {"version": "1.5.0"}),
            ]
            # Should NOT raise.
            run_cross_service_version_check()

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",  # no requirement
    )
    def test_raises_when_dq_too_old(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _stub_httpx_response(
                200, {"version": "1.2.2"}
            )
            with pytest.raises(
                ImproperlyConfigured,
                match=r"dq-service: reported version '1.2.2' is less than",
            ):
                run_cross_service_version_check()

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",
    )
    def test_raises_when_dq_unreachable(self):
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            with pytest.raises(
                ImproperlyConfigured,
                match=r"dq-service: unreachable",
            ):
                run_cross_service_version_check()

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",
    )
    def test_raises_when_response_missing_version_field(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _stub_httpx_response(
                200, {"some_other_field": "value"}
            )
            with pytest.raises(
                ImproperlyConfigured,
                match=r"without a 'version' string field",
            ):
                run_cross_service_version_check()

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="",  # missing!
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
    )
    def test_raises_when_url_setting_missing_in_production(self):
        with pytest.raises(
            ImproperlyConfigured,
            match=r"DQ_SERVICE_URL is not configured",
        ):
            run_cross_service_version_check()


class TestVersionCheckNonProduction:
    """Non-production environments — failures degrade to warnings."""

    @override_settings(
        ENVIRONMENT="development",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",
    )
    def test_does_not_raise_when_dq_too_old_in_dev(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _stub_httpx_response(
                200, {"version": "1.0.0"}
            )
            # No raise — warning logged instead.
            run_cross_service_version_check()

    @override_settings(
        ENVIRONMENT="development",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="1.2.3",
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",
    )
    def test_does_not_raise_when_unreachable_in_dev(self):
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            # No raise.
            run_cross_service_version_check()


class TestVersionCheckMasterSwitch:
    """The CROSS_SERVICE_VERSION_CHECK_ENABLED master switch overrides
    the production default."""

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=False,  # explicitly disabled
        DQ_SERVICE_URL="http://dq:8083",
        HUB_REQUIRED_DQ_SERVICE_VERSION="999.0.0",  # unreachable requirement
    )
    def test_disabled_skips_check_even_in_production(self):
        with patch("httpx.get") as mock_get:
            # If the check ran, this would be called and the version-too-old
            # branch would raise. We assert it's NOT called.
            run_cross_service_version_check()
            mock_get.assert_not_called()

    @override_settings(
        ENVIRONMENT="production",
        CROSS_SERVICE_VERSION_CHECK_ENABLED=True,
        DQ_SERVICE_URL="http://dq:8083",
        COMPLIANCE_SERVICE_URL="http://compliance:8082",
        HUB_REQUIRED_DQ_SERVICE_VERSION="0.0.0",  # no requirement
        HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION="0.0.0",
    )
    def test_no_required_version_skips_probe(self):
        with patch("httpx.get") as mock_get:
            # When required version is "0.0.0" (sentinel), no HTTP probe.
            run_cross_service_version_check()
            mock_get.assert_not_called()
