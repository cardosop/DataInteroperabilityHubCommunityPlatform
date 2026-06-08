"""Unit tests for typed CLI errors (278.AA.13)."""
import pytest

from datahub_cli.errors import (
    CLIError,
    CLIAuthError,
    CLIConfigError,
    CLINetworkError,
    CLINotFoundError,
    CLIRateLimitError,
    CLIServerError,
    CLIValidationError,
    error_from_http_status,
    EX_DATAERR,
    EX_TEMPFAIL,
    EX_UNAVAILABLE,
)


class TestErrorHierarchy:
    @pytest.mark.unit
    def test_base_is_click_exception(self):
        err = CLIError("msg")
        from click import ClickException
        assert isinstance(err, ClickException)

    @pytest.mark.unit
    def test_exit_codes_are_distinct(self):
        codes = {
            CLIError.exit_code,
            CLIAuthError.exit_code,
            CLINotFoundError.exit_code,
            CLIValidationError.exit_code,
            CLINetworkError.exit_code,
            CLIServerError.exit_code,
            CLIRateLimitError.exit_code,
            CLIConfigError.exit_code,
        }
        # 8 error classes, 7 distinct exit codes:
        # CLINetworkError and CLIRateLimitError intentionally share
        # EX_TEMPFAIL = 75 (both are transient failures).
        assert len(codes) == 7, (
            f"Expected 7 distinct exit codes, got {len(codes)}: {codes}"
        )

    @pytest.mark.unit
    def test_error_codes_carried(self):
        err = CLIError("msg", "TEST_CODE")
        assert err.error_code == "TEST_CODE"

    @pytest.mark.unit
    def test_format_includes_code(self):
        err = CLIError("something broke", "E001")
        assert "[E001]" in err.format_message()
        assert "something broke" in err.format_message()


class TestErrorFromHttpStatus:
    @pytest.mark.unit
    def test_401_returns_auth_error(self):
        err = error_from_http_status(401, "unauthorized")
        assert isinstance(err, CLIAuthError)

    @pytest.mark.unit
    def test_403_returns_auth_error(self):
        err = error_from_http_status(403, "forbidden")
        assert isinstance(err, CLIAuthError)

    @pytest.mark.unit
    def test_404_returns_not_found(self):
        err = error_from_http_status(404, "missing")
        assert isinstance(err, CLINotFoundError)

    @pytest.mark.unit
    def test_422_returns_validation_error(self):
        err = error_from_http_status(422, "invalid")
        assert isinstance(err, CLIValidationError)

    @pytest.mark.unit
    def test_400_returns_validation_error(self):
        err = error_from_http_status(400, "bad request")
        assert isinstance(err, CLIValidationError)

    @pytest.mark.unit
    def test_429_returns_rate_limit(self):
        err = error_from_http_status(429, "slow down")
        assert isinstance(err, CLIRateLimitError)

    @pytest.mark.unit
    def test_500_returns_server_error(self):
        err = error_from_http_status(500, "boom")
        assert isinstance(err, CLIServerError)

    @pytest.mark.unit
    def test_503_returns_server_error(self):
        err = error_from_http_status(503, "unavailable")
        assert isinstance(err, CLIServerError)

    @pytest.mark.unit
    def test_unknown_status_returns_base(self):
        err = error_from_http_status(308, "redirect")
        assert isinstance(err, CLIError)
        assert not isinstance(err, (CLIAuthError, CLINotFoundError, CLIValidationError))
