"""
Test Environment Configuration Validation

Comprehensive validation of test environment variables, URLs, and service connectivity.
This module ensures all required test infrastructure is properly configured before tests run.

Following TDD approach - tests are written first, then implementation.
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import pytest


class EnvironmentValidationError(Exception):
    """Raised when test environment validation fails"""
    pass


class EnvironmentValidator:
    """
    Validates test environment configuration including:
    - Required environment variables
    - URL format validation
    - Service connectivity validation

    Automatically detects Docker environments and uses appropriate service URLs.
    """

    # Required environment variables for test environment
    REQUIRED_DATABASE_VARS = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]

    REQUIRED_REDIS_VARS = [
        "REDIS_URL",
    ]

    REQUIRED_SERVICE_VARS = [
        "DATACONTRACT_SERVICE_URL",
        "DQ_SERVICE_URL",
        "COMPLIANCE_SERVICE_URL",
        "SEMANTIC_SERVICE_URL",
    ]

    REQUIRED_AUTH_VARS = [
        "SECRET_KEY",
        "JWT_SECRET_KEY",
    ]

    # Docker service name mappings (for auto-detection)
    DOCKER_SERVICE_MAPPINGS = {
        "DATACONTRACT_SERVICE_URL": {
            "service_name": "datacontract-service",
            "default_port": 8080,
            "staging_port": 8080,  # Internal port in staging
        },
        "DQ_SERVICE_URL": {
            "service_name": "dq-service",
            "default_port": 8083,
            "staging_port": 8083,
        },
        "COMPLIANCE_SERVICE_URL": {
            "service_name": "compliance-service",
            "default_port": 8082,
            "staging_port": 8082,
        },
        "SEMANTIC_SERVICE_URL": {
            "service_name": "semantic-service",
            "default_port": 8081,
            "staging_port": 8081,
        },
    }

    # Optional feature flags (with defaults)
    FEATURE_FLAGS = [
        "OPENTELEMETRY_ENABLED",
        "EMAIL_JOB_NOTIFICATIONS_ENABLED",
        "USE_S3",
        "DEBUG",
    ]

    def __init__(self, strict: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, fail on missing required variables. If False, warn only.
        """
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._is_docker = self._detect_docker_environment()
        self._environment = os.getenv("ENVIRONMENT", "").lower()

    def _detect_docker_environment(self) -> bool:
        """
        Detect if running in Docker environment.

        Returns:
            True if running in Docker, False otherwise
        """
        # Check for /.dockerenv file (standard Docker indicator)
        if os.path.exists("/.dockerenv"):
            return True

        # Check for Docker-related environment variables
        if os.getenv("DOCKER_CONTAINER") or os.getenv("DOCKER_COMPOSE"):
            return True

        # Check if we're in a container by looking at cgroup
        try:
            with open("/proc/self/cgroup", "r") as f:
                content = f.read()
                if "docker" in content or "containerd" in content:
                    return True
        except (FileNotFoundError, PermissionError):
            pass

        return False

    def _get_docker_service_url(self, var_name: str) -> Optional[str]:
        """
        Get Docker service URL for a given environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            Docker service URL or None if not applicable
        """
        if not self._is_docker:
            return None

        if var_name not in self.DOCKER_SERVICE_MAPPINGS:
            return None

        mapping = self.DOCKER_SERVICE_MAPPINGS[var_name]
        service_name = mapping["service_name"]

        # Use staging port if in staging environment, otherwise default port
        if self._environment == "staging":
            port = mapping.get("staging_port", mapping["default_port"])
        else:
            port = mapping["default_port"]

        # In Docker, services are accessible via service names
        return f"http://{service_name}:{port}"

    def _get_effective_service_url(self, var_name: str) -> Optional[str]:
        """
        Get effective service URL, checking environment variable first,
        then falling back to Docker service URL if in Docker environment.

        Args:
            var_name: Environment variable name

        Returns:
            Service URL or None
        """
        # First check if explicitly set
        url = os.getenv(var_name)
        if url and url.strip():
            return url.strip()

        # If in Docker and not explicitly set, use Docker service URL
        if self._is_docker:
            docker_url = self._get_docker_service_url(var_name)
            if docker_url:
                return docker_url

        return None

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validation checks.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors.clear()
        self.warnings.clear()

        # Validate required variables (with Docker auto-detection)
        self._validate_required_variables()

        # Validate URL formats
        self._validate_url_formats()

        # Validate service connectivity (if services are configured)
        self._validate_service_connectivity()

        # In non-strict mode, is_valid should be False if there are warnings about missing critical vars
        # Critical vars (database, redis, auth) always cause validation to fail
        # Service URLs can be auto-detected in Docker, so they don't cause validation failure
        has_critical_missing = any(
            "Missing required environment variables" in error or
            any(var in error for var in self.REQUIRED_DATABASE_VARS + self.REQUIRED_REDIS_VARS + self.REQUIRED_AUTH_VARS)
            for error in self.errors
        ) or any(
            "Missing required environment variables" in warning or
            any(var in warning for var in self.REQUIRED_DATABASE_VARS + self.REQUIRED_REDIS_VARS + self.REQUIRED_AUTH_VARS)
            for warning in self.warnings
        )

        # Validation fails if there are errors OR if critical vars are missing (even as warnings in non-strict mode)
        is_valid = len(self.errors) == 0 and not has_critical_missing
        return is_valid, self.errors.copy(), self.warnings.copy()

    def _validate_required_variables(self) -> None:
        """Check that all required environment variables are set"""
        # Database and Redis vars are always required
        critical_vars = (
            self.REQUIRED_DATABASE_VARS +
            self.REQUIRED_REDIS_VARS +
            self.REQUIRED_AUTH_VARS
        )

        missing_critical = []
        for var in critical_vars:
            value = os.getenv(var)
            if not value or value.strip() == "":
                missing_critical.append(var)

        # Service URLs can be auto-detected in Docker
        missing_services = []
        for var in self.REQUIRED_SERVICE_VARS:
            effective_url = self._get_effective_service_url(var)
            if not effective_url:
                missing_services.append(var)

        all_missing = missing_critical + missing_services

        # In Docker, auto-detect service URLs if not explicitly set
        if self._is_docker and missing_services:
            auto_detected = []
            for var in missing_services[:]:  # Copy list to iterate safely
                docker_url = self._get_docker_service_url(var)
                if docker_url:
                    auto_detected.append(f"{var} (auto-detected: {docker_url})")
                    # Set it in environment for this session (but don't remove from missing list yet)
                    os.environ[var] = docker_url
                    # Remove from missing_services list since we auto-detected it
                    missing_services.remove(var)

            if auto_detected:
                self.warnings.append(
                    f"Service URLs auto-detected in Docker: {', '.join(auto_detected)}"
                )

        # Recalculate all_missing after auto-detection
        all_missing = missing_critical + missing_services

        if all_missing:
            error_msg = f"Missing required environment variables: {', '.join(all_missing)}"
            if self.strict:
                self.errors.append(error_msg)
            else:
                self.warnings.append(error_msg)

    def _validate_url_formats(self) -> None:
        """Validate URL format for all URL environment variables"""
        url_vars = {
            "REDIS_URL": os.getenv("REDIS_URL"),
            "DATACONTRACT_SERVICE_URL": self._get_effective_service_url("DATACONTRACT_SERVICE_URL"),
            "DQ_SERVICE_URL": self._get_effective_service_url("DQ_SERVICE_URL"),
            "COMPLIANCE_SERVICE_URL": self._get_effective_service_url("COMPLIANCE_SERVICE_URL"),
            "SEMANTIC_SERVICE_URL": self._get_effective_service_url("SEMANTIC_SERVICE_URL"),
        }

        for var_name, url_value in url_vars.items():
            if not url_value:
                continue

            if not self._is_valid_url(url_value):
                error_msg = f"Invalid URL format for {var_name}: {url_value}"
                if self.strict:
                    self.errors.append(error_msg)
                else:
                    self.warnings.append(error_msg)

    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format.

        Supports:
        - http://host:port/path
        - https://host:port/path
        - redis://host:port/db
        - postgresql://user:pass@host:port/db
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)
            # Must have scheme
            if not parsed.scheme:
                return False

            # Redis URLs can be redis://host:port/db
            if parsed.scheme == "redis":
                return bool(parsed.netloc)

            # HTTP/HTTPS URLs must have netloc
            if parsed.scheme in ("http", "https"):
                return bool(parsed.netloc)

            # PostgreSQL URLs
            if parsed.scheme in ("postgresql", "postgres"):
                return bool(parsed.netloc)

            return False
        except Exception:
            return False

    def _validate_service_connectivity(self) -> None:
        """
        Validate connectivity to services.
        Checks configuration and attempts basic connectivity tests.
        """
        # Database connectivity check
        self._check_database_config()

        # Redis connectivity check
        self._check_redis_config()

        # Service URLs check (format already validated, just verify they're set)
        service_vars = {
            "DATACONTRACT_SERVICE_URL": self._get_effective_service_url("DATACONTRACT_SERVICE_URL"),
            "DQ_SERVICE_URL": self._get_effective_service_url("DQ_SERVICE_URL"),
            "COMPLIANCE_SERVICE_URL": self._get_effective_service_url("COMPLIANCE_SERVICE_URL"),
            "SEMANTIC_SERVICE_URL": self._get_effective_service_url("SEMANTIC_SERVICE_URL"),
        }

        for var_name, url_value in service_vars.items():
            if not url_value:
                warning = f"Service URL not configured: {var_name}"
                if self._is_docker:
                    docker_url = self._get_docker_service_url(var_name)
                    if docker_url:
                        warning += f" (Docker auto-detection available: {docker_url})"
                self.warnings.append(warning)

    def validate_database_connectivity(self, timeout: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Validate database connectivity.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            Tuple of (is_connected, error_message)
        """
        try:
            import psycopg2
        except ImportError:
            return False, "psycopg2 not installed"

        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        db = os.getenv("POSTGRES_DB")

        if not all([host, port, user, password, db]):
            return False, "Database configuration incomplete"

        try:
            conn = psycopg2.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=db,
                connect_timeout=timeout,
            )
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)

    def validate_redis_connectivity(self, timeout: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Validate Redis connectivity.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            Tuple of (is_connected, error_message)
        """
        try:
            import redis
        except ImportError:
            return False, "redis not installed"

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return False, "REDIS_URL not configured"

        try:
            r = redis.from_url(redis_url, socket_connect_timeout=timeout)
            r.ping()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_service_url(self, var_name: str) -> Optional[str]:
        """
        Get service URL for a given variable name, with Docker auto-detection.

        Args:
            var_name: Environment variable name

        Returns:
            Service URL or None
        """
        return self._get_effective_service_url(var_name)

    def validate_service_connectivity(
        self, service_url: str, timeout: int = 5
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate HTTP service connectivity.

        Args:
            service_url: Service URL to check
            timeout: Request timeout in seconds

        Returns:
            Tuple of (is_connected, error_message)
        """
        if not service_url:
            return False, "Service URL not provided"

        try:
            import httpx
        except ImportError:
            try:
                import requests
            except ImportError:
                return False, "httpx or requests not installed"
            else:
                # Use requests
                try:
                    response = requests.get(
                        f"{service_url}/health", timeout=timeout, allow_redirects=False
                    )
                    # Accept 200, 301, 302, 503 (service exists even if unhealthy)
                    if response.status_code in [200, 301, 302, 503]:
                        return True, None
                    return False, f"Service returned status {response.status_code}"
                except Exception as e:
                    return False, str(e)

        # Use httpx
        try:
            response = httpx.get(f"{service_url}/health", timeout=timeout, follow_redirects=False)
            # Accept 200, 301, 302, 503 (service exists even if unhealthy)
            if response.status_code in [200, 301, 302, 503]:
                return True, None
            return False, f"Service returned status {response.status_code}"
        except Exception as e:
            return False, str(e)

    def _check_database_config(self) -> None:
        """Validate database configuration"""
        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        db = os.getenv("POSTGRES_DB")

        if not all([host, port, user, password, db]):
            return  # Already handled by required vars check

        # Validate port is numeric
        try:
            int(port)
        except (ValueError, TypeError):
            error_msg = f"Invalid POSTGRES_PORT: {port} (must be numeric)"
            if self.strict:
                self.errors.append(error_msg)
            else:
                self.warnings.append(error_msg)

    def _check_redis_config(self) -> None:
        """Validate Redis configuration"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return  # Already handled by required vars check

        # Redis URL format: redis://host:port/db
        if not redis_url.startswith("redis://"):
            error_msg = f"REDIS_URL must start with 'redis://': {redis_url}"
            if self.strict:
                self.errors.append(error_msg)
            else:
                self.warnings.append(error_msg)


def validate_test_environment(strict: bool = True) -> Tuple[bool, List[str], List[str]]:
    """
    Convenience function to validate test environment.

    Args:
        strict: If True, raise exception on validation failure. If False, return warnings.

    Returns:
        Tuple of (is_valid, errors, warnings)

    Raises:
        EnvironmentValidationError: If validation fails and strict=True
    """
    validator = EnvironmentValidator(strict=strict)
    is_valid, errors, warnings = validator.validate_all()

    if not is_valid and strict:
        error_msg = "Test environment validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        if warnings:
            error_msg += "\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)
        raise EnvironmentValidationError(error_msg)

    return is_valid, errors, warnings


# Backward compatibility aliases
TestEnvironmentValidator = EnvironmentValidator
TestEnvironmentValidationError = EnvironmentValidationError

