"""
Tests for test environment validation module.

Following TDD approach - tests define expected behavior.
"""

import pytest

from tests.utils.test_environment_validation import (
    TestEnvironmentValidationError,
    # Backward compatibility
    TestEnvironmentValidator,
    validate_test_environment,
)


class TestTestEnvironmentValidator:
    """Test TestEnvironmentValidator class"""

    def test_validate_all_with_valid_environment(self, monkeypatch):
        """Test validation passes with valid environment variables"""
        # Set all required variables
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("DATACONTRACT_SERVICE_URL", "http://localhost:8080")
        monkeypatch.setenv("DQ_SERVICE_URL", "http://localhost:8083")
        monkeypatch.setenv("COMPLIANCE_SERVICE_URL", "http://localhost:8082")
        monkeypatch.setenv("SEMANTIC_SERVICE_URL", "http://localhost:8081")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key")

        validator = TestEnvironmentValidator(strict=True)
        is_valid, errors, _warnings = validator.validate_all()

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_with_missing_required_vars(self, monkeypatch):
        """Test validation fails with missing required variables"""
        # Clear all environment variables
        for var in TestEnvironmentValidator.REQUIRED_DATABASE_VARS:
            monkeypatch.delenv(var, raising=False)
        for var in TestEnvironmentValidator.REQUIRED_REDIS_VARS:
            monkeypatch.delenv(var, raising=False)
        for var in TestEnvironmentValidator.REQUIRED_SERVICE_VARS:
            monkeypatch.delenv(var, raising=False)
        for var in TestEnvironmentValidator.REQUIRED_AUTH_VARS:
            monkeypatch.delenv(var, raising=False)

        validator = TestEnvironmentValidator(strict=True)
        is_valid, errors, _warnings = validator.validate_all()

        assert is_valid is False
        assert len(errors) > 0
        assert any("Missing required environment variables" in error for error in errors)

    def test_validate_all_with_invalid_url_format(self, monkeypatch):
        """Test validation fails with invalid URL format"""
        # Set required vars
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("REDIS_URL", "invalid-url")
        monkeypatch.setenv("DATACONTRACT_SERVICE_URL", "http://localhost:8080")
        monkeypatch.setenv("DQ_SERVICE_URL", "http://localhost:8083")
        monkeypatch.setenv("COMPLIANCE_SERVICE_URL", "http://localhost:8082")
        monkeypatch.setenv("SEMANTIC_SERVICE_URL", "http://localhost:8081")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key")

        validator = TestEnvironmentValidator(strict=True)
        is_valid, errors, _warnings = validator.validate_all()

        assert is_valid is False
        assert any("Invalid URL format" in error for error in errors)

    def test_validate_all_with_invalid_port(self, monkeypatch):
        """Test validation fails with invalid port number"""
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "invalid-port")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("DATACONTRACT_SERVICE_URL", "http://localhost:8080")
        monkeypatch.setenv("DQ_SERVICE_URL", "http://localhost:8083")
        monkeypatch.setenv("COMPLIANCE_SERVICE_URL", "http://localhost:8082")
        monkeypatch.setenv("SEMANTIC_SERVICE_URL", "http://localhost:8081")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key")

        validator = TestEnvironmentValidator(strict=True)
        is_valid, errors, _warnings = validator.validate_all()

        assert is_valid is False
        assert any("Invalid POSTGRES_PORT" in error for error in errors)

    def test_validate_all_non_strict_mode(self, monkeypatch):
        """Test validation in non-strict mode generates warnings instead of errors"""
        # Clear some variables
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)

        validator = TestEnvironmentValidator(strict=False)
        _is_valid, errors, warnings = validator.validate_all()

        # In non-strict mode, missing vars generate warnings, not errors
        assert len(errors) == 0
        assert len(warnings) > 0

    def test_is_valid_url_http(self):
        """Test URL validation for HTTP URLs"""
        validator = TestEnvironmentValidator()
        assert validator._is_valid_url("http://localhost:8080") is True
        assert validator._is_valid_url("http://localhost:8080/health") is True
        assert validator._is_valid_url("https://example.com") is True
        assert validator._is_valid_url("invalid-url") is False
        assert validator._is_valid_url("") is False
        assert validator._is_valid_url(None) is False

    def test_is_valid_url_redis(self):
        """Test URL validation for Redis URLs"""
        validator = TestEnvironmentValidator()
        assert validator._is_valid_url("redis://localhost:6379/0") is True
        assert validator._is_valid_url("redis://localhost:6379") is True
        assert validator._is_valid_url("redis://redis:6379/0") is True
        assert validator._is_valid_url("invalid-redis-url") is False

    def test_is_valid_url_postgresql(self):
        """Test URL validation for PostgreSQL URLs"""
        validator = TestEnvironmentValidator()
        assert validator._is_valid_url("postgresql://user:pass@host:5432/db") is True
        assert validator._is_valid_url("postgres://user:pass@host:5432/db") is True


class TestValidateTestEnvironment:
    """Test validate_test_environment convenience function"""

    def test_validate_test_environment_success(self, monkeypatch):
        """Test validate_test_environment succeeds with valid environment"""
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("DATACONTRACT_SERVICE_URL", "http://localhost:8080")
        monkeypatch.setenv("DQ_SERVICE_URL", "http://localhost:8083")
        monkeypatch.setenv("COMPLIANCE_SERVICE_URL", "http://localhost:8082")
        monkeypatch.setenv("SEMANTIC_SERVICE_URL", "http://localhost:8081")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key")

        is_valid, errors, _warnings = validate_test_environment(strict=True)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_test_environment_failure_strict(self, monkeypatch):
        """Test validate_test_environment raises exception in strict mode"""
        # Clear required variables
        for var in TestEnvironmentValidator.REQUIRED_DATABASE_VARS:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(TestEnvironmentValidationError) as exc_info:
            validate_test_environment(strict=True)

        assert "Test environment validation failed" in str(exc_info.value)

    def test_validate_test_environment_failure_non_strict(self, monkeypatch):
        """Test validate_test_environment returns False in non-strict mode"""
        # Clear required variables
        for var in TestEnvironmentValidator.REQUIRED_DATABASE_VARS:
            monkeypatch.delenv(var, raising=False)

        is_valid, errors, warnings = validate_test_environment(strict=False)
        assert is_valid is False
        assert len(errors) == 0  # Errors become warnings in non-strict mode
        assert len(warnings) > 0
