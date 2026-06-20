"""Unit tests for SDK client retry logic (279.E.3). No backend needed."""

import pytest

from datahub_interoperability.client import calculate_backoff_delay, is_retryable_error
from datahub_interoperability.errors import (
    DataHubError,
    NetworkError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class TestCalculateBackoffDelay:
    @pytest.mark.parametrize(
        "attempt,base_delay,expected",
        [
            (0, 1.0, 1.0),
            (1, 1.0, 2.0),
            (2, 1.0, 4.0),
            (4, 1.0, 16.0),
            (2, 3.0, 12.0),
        ],
    )
    def test_exponential_backoff(self, attempt, base_delay, expected):
        assert calculate_backoff_delay(attempt, base_delay=base_delay) == expected


class TestIsRetryableError:
    @pytest.mark.parametrize(
        "error,expected",
        [
            (NetworkError("timeout"), True),
            (ServerError("boom", http_status=500), True),
            (ServerError("unavailable", http_status=503), True),
            (RateLimitError("slow down"), True),
            (ValidationError("bad input"), False),
            (DataHubError("missing", "NOT_FOUND", 404), False),
            (DataHubError("auth", "UNAUTHORIZED", 401), False),
            (ValueError("not our error"), False),
        ],
    )
    def test_is_retryable_error(self, error, expected):
        assert is_retryable_error(error) is expected
