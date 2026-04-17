"""
Tests for StandardErrorCodes completeness and consistency.

Ensures every domain-specific error code referenced in the docs
actually exists in the code, and that the STATUS_TO_CODE mapping
covers all standard HTTP error statuses.
"""

import pytest
from rest_framework import status

from hub.apps.api.standards.error_codes import StandardErrorCodes, get_error_code


class TestStandardErrorCodesCompleteness:
    """Verify every documented error code is defined."""

    DOCUMENTED_CODES = [
        "ASSET_NOT_FOUND",
        "CONTRACT_VALIDATION_FAILED",
        "DQ_CHECK_FAILED",
        "COMPLIANCE_SCAN_FAILED",
        "MVP_FEATURE_GATED",
        "QUOTA_EXCEEDED",
        "TENANT_NOT_FOUND",
        "WEBHOOK_DELIVERY_FAILED",
        "AUTH_TOKEN_EXPIRED",
        "RATE_LIMIT_EXCEEDED",
    ]

    @pytest.mark.parametrize("code", DOCUMENTED_CODES)
    def test_documented_code_exists(self, code):
        """Every code listed in docs/mvpdocs/reference/error-codes.md must exist."""
        assert hasattr(StandardErrorCodes, code), (
            f"StandardErrorCodes is missing '{code}' — documented in error-codes.md"
        )
        assert getattr(StandardErrorCodes, code) == code

    def test_status_to_code_covers_standard_statuses(self):
        """STATUS_TO_CODE must map every standard error HTTP status."""
        required = [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_409_CONFLICT,
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
        for code in required:
            assert code in StandardErrorCodes.STATUS_TO_CODE, (
                f"STATUS_TO_CODE missing mapping for HTTP {code}"
            )

    def test_get_error_code_returns_string(self):
        """get_error_code always returns a non-empty string."""
        result = get_error_code(http_status=status.HTTP_404_NOT_FOUND)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_error_code_fallback(self):
        """Unknown status falls back to INTERNAL_ERROR."""
        result = get_error_code(http_status=599)
        assert result == StandardErrorCodes.INTERNAL_ERROR
