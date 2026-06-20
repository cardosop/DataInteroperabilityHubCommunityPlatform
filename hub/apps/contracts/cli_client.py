"""
DataContract CLI Service Client

Client for interacting with the DataContract CLI service.

**Important Notes:**
- This client calls an EXTERNAL microservice (datacontract-service), not Django API endpoints
- Endpoints are microservice-specific paths (e.g., '/validate', '/lint', '/convert')
- For Django API endpoint construction, use `hub.apps.api.utils.api_url_builder.APIURLBuilder`
- This client follows service-to-service communication patterns with circuit breaker protection
"""

import hashlib
from typing import Any

import httpx
import structlog
from django.conf import settings
from django.core.cache import cache

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = structlog.get_logger(__name__)

# Default timeout for CLI operations
DEFAULT_TIMEOUT = 60
SYNC_TIMEOUT = 60  # For synchronous validation
ASYNC_TIMEOUT = 300  # For asynchronous validation (via jobs)


class DataContractCLIClient:
    """
    Client for DataContract CLI service.

    Handles validation, linting, and conversion operations.
    """

    def __init__(self):
        """Initialize client with service URL from settings"""
        import os
        import sys

        # In test environment, use localhost instead of service name
        default_url = "http://datacontract-service:8080"
        if hasattr(settings, "TESTING") and settings.TESTING:
            if os.getenv("TEST_ENVIRONMENT") == "staging":
                default_url = "http://localhost:8092"  # Staging uses port 8092
            elif os.getenv("TEST_ENVIRONMENT") == "default":
                default_url = "http://localhost:8080"
        if "pytest" in sys.modules or "unittest" in sys.modules:
            # Auto-detect staging vs default
            import httpx

            try:
                # Check if staging port is accessible
                response = httpx.get("http://localhost:8092/health", timeout=1)
                if response.status_code == 200:
                    default_url = "http://localhost:8092"
                else:
                    default_url = "http://localhost:8080"
            except (httpx.RequestError, OSError):
                # Network / connection errors → fall back to standard port.
                default_url = "http://localhost:8080"

        # Support both variable names for compatibility
        self.base_url = getattr(
            settings,
            "DATACONTRACT_SERVICE_URL",
            getattr(settings, "DATACONTRACT_CLI_SERVICE_URL", default_url),
        )
        self.timeout = getattr(settings, "DATACONTRACT_SERVICE_TIMEOUT", DEFAULT_TIMEOUT)

        # Initialize circuit breaker with 30-second timeout
        self._circuit_breaker = CircuitBreaker(
            service_name="datacontract-service",
            failure_threshold=5,
            timeout_seconds=30,  # 30 seconds as specified
            success_threshold=2,
            redis_client=get_redis_client(),
        )

    def _make_request(
        self, endpoint: str, data: dict[str, Any], timeout: int | None = None, max_retries: int = 2
    ) -> dict[str, Any]:
        """
        Make HTTP request to DataContract service with retry logic.

        Args:
            endpoint: API endpoint (e.g., '/validate')
            data: Request payload
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for transient failures

        Returns:
            Response JSON as dictionary

        Raises:
            Exception: On HTTP errors or timeout after retries
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.timeout

        # Build request headers — include internal API key for service-to-service auth
        request_headers: dict[str, str] = {}
        internal_key = getattr(settings, "INTERNAL_API_KEY", "")
        if internal_key:
            request_headers["X-Internal-Api-Key"] = internal_key

        # Retry logic with exponential backoff
        backoff_delays = [1, 3]  # 1s, 3s

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=data, headers=request_headers)
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException as e:
                if attempt < max_retries:
                    delay = (
                        backoff_delays[attempt]
                        if attempt < len(backoff_delays)
                        else backoff_delays[-1]
                    )
                    logger.warning(
                        "datacontract_service_timeout_retry",
                        endpoint=endpoint,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                    )
                    import time

                    time.sleep(delay)
                    continue
                logger.warning("datacontract_service_timeout", endpoint=endpoint, timeout=timeout)
                raise Exception(
                    f"DataContract service timeout after {timeout}s (after {max_retries} retries)"
                ) from e
            except httpx.HTTPStatusError as e:
                # Don't retry on client errors (4xx)
                if e.response.status_code < 500:
                    logger.warning(
                        "datacontract_service_client_error",
                        endpoint=endpoint,
                        status_code=e.response.status_code,
                    )
                    raise Exception(
                        f"DataContract service client error: {e.response.status_code}"
                    ) from e
                # Retry on server errors (5xx)
                if attempt < max_retries:
                    delay = (
                        backoff_delays[attempt]
                        if attempt < len(backoff_delays)
                        else backoff_delays[-1]
                    )
                    logger.warning(
                        "datacontract_service_server_error_retry",
                        endpoint=endpoint,
                        status_code=e.response.status_code,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                    )
                    import time

                    time.sleep(delay)
                    continue
                logger.error(
                    "datacontract_service_server_error",
                    endpoint=endpoint,
                    status_code=e.response.status_code,
                )
                raise Exception(
                    f"DataContract service server error: {e.response.status_code}"
                ) from e
            except httpx.HTTPError as e:
                if attempt < max_retries:
                    delay = (
                        backoff_delays[attempt]
                        if attempt < len(backoff_delays)
                        else backoff_delays[-1]
                    )
                    logger.warning(
                        "datacontract_service_error_retry",
                        endpoint=endpoint,
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                    )
                    import time

                    time.sleep(delay)
                    continue
                logger.warning("datacontract_service_error", endpoint=endpoint, error=str(e))
                raise Exception(f"DataContract service error: {e!s}") from e

        raise Exception(f"DataContract service failed after {max_retries} retries")

    def _compute_contract_hash(self, raw_contract: str, format: str) -> str:
        """
        Compute hash for contract caching.

        Args:
            raw_contract: Raw contract content
            format: Contract format (JSON or YAML)

        Returns:
            SHA-256 hash as hex string
        """
        content = f"{format}:{raw_contract}".encode()
        return hashlib.sha256(content).hexdigest()

    def _get_cache_key(self, contract_hash: str, cli_version: str, operation: str) -> str:
        """Generate cache key for validation result"""
        return f"datacontract:{operation}:{contract_hash}:{cli_version}"

    def validate(
        self,
        raw_contract: str,
        format: str,
        tenant_id: str | None = None,
        use_cache: bool = True,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Validate a contract.

        In test environment, returns a mock response to prevent timeouts.

        Args:
            raw_contract: Raw contract content
            format: Contract format (JSON or YAML)
            tenant_id: Tenant ID for caching
            use_cache: Whether to use cached results
            timeout: Request timeout in seconds

        Returns:
            Validation result with status, issues, cli_version
        """
        # Compute contract hash
        contract_hash = self._compute_contract_hash(raw_contract, format)

        # Check cache if enabled
        if use_cache:
            # Get CLI version first (for cache key)
            try:
                health = self.health_check()
                cli_version = health.get("cli_version", "unknown")
                cache_key = self._get_cache_key(contract_hash, cli_version, "validate")
                cached_result = cache.get(cache_key)
                if cached_result:
                    logger.info("datacontract_validation_cache_hit", contract_hash=contract_hash)
                    return cached_result
            except (httpx.RequestError, OSError):
                pass  # Continue with validation if cache/health check fails

        # Define fallback response
        def fallback_response(*args, **kwargs) -> dict[str, Any]:
            """Fallback response when circuit breaker is open or service fails."""
            return {
                "validation_status": "ERROR",
                "issues": [],
                "cli_version": "unknown",
                "error": "DataContract service unavailable (circuit breaker open)",
            }

        # Execute with circuit breaker protection
        def execute_validation() -> dict[str, Any]:
            """Execute validation operation."""
            # Make validation request
            request_data = {
                "raw_contract": raw_contract,
                "format": format.lower(),
                "timeout": timeout or SYNC_TIMEOUT,
                "tenant_id": tenant_id,
                "use_cache": use_cache,
            }

            result = self._make_request("/validate", request_data, timeout=timeout or SYNC_TIMEOUT)

            # Cache result if enabled
            if use_cache and "cli_version" in result:
                cache_key = self._get_cache_key(contract_hash, result["cli_version"], "validate")
                cache.set(cache_key, result, timeout=3600)  # Cache for 1 hour

            return result

        try:
            result = self._circuit_breaker.call(execute_validation, fallback=fallback_response)
            return result
        except Exception as e:
            # The underlying _make_request / circuit-breaker call already
            # logged the specific failure mode at the appropriate level.
            # This catch-all returns a fallback response (graceful
            # degradation), so log at WARNING — not ERROR — since the
            # caller is expected to handle the fallback.
            logger.warning("datacontract_validation_error", error=str(e), endpoint="/validate")
            return fallback_response()

    def lint(self, raw_contract: str, format: str, timeout: int | None = None) -> dict[str, Any]:
        """
        Lint a contract.

        Args:
            raw_contract: Raw contract content
            format: Contract format (JSON or YAML)
            timeout: Request timeout in seconds

        Returns:
            Linting result with issues
        """
        request_data = {
            "raw_contract": raw_contract,
            "format": format.lower(),
            "timeout": timeout or SYNC_TIMEOUT,
        }

        return self._make_request("/lint", request_data, timeout=timeout or SYNC_TIMEOUT)

    def convert(
        self, raw_contract: str, source_format: str, target_format: str, timeout: int | None = None
    ) -> dict[str, Any]:
        """
        Convert a contract between formats.

        Args:
            raw_contract: Raw contract content
            source_format: Source format (JSON or YAML)
            target_format: Target format (JSON or YAML)
            timeout: Request timeout in seconds

        Returns:
            Conversion result with converted contract
        """
        request_data = {
            "raw_contract": raw_contract,
            "source_format": source_format.lower(),
            "target_format": target_format.lower(),
            "timeout": timeout or SYNC_TIMEOUT,
        }

        return self._make_request("/convert", request_data, timeout=timeout or SYNC_TIMEOUT)

    def health_check(self) -> dict[str, Any]:
        """
        Check service health and get CLI version.

        Returns:
            Health status and CLI version
        """
        try:
            url = f"{self.base_url}/health"
            with httpx.Client(timeout=5) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning("datacontract_service_health_check_failed", error=str(e))
            return {"status": "unhealthy", "cli_version": "unknown"}


def interpret_validation_status(
    validation_result: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Interpret validation result into status and structured errors/warnings.

    Args:
        validation_result: Result from DataContract CLI service

    Returns:
        Tuple of (validation_status, errors, warnings)
    """
    validation_status = validation_result.get("validation_status", "ERROR")
    issues = validation_result.get("issues", [])

    errors = []
    warnings = []

    for issue in issues:
        severity = issue.get("severity", "INFO")
        structured_issue = {
            "severity": severity,
            "category": issue.get("category", "unknown"),
            "path": issue.get("path", ""),
            "message": issue.get("message", ""),
            "rule_id": issue.get("rule_id", ""),
        }

        if severity in ["ERROR", "CRITICAL"]:
            errors.append(structured_issue)
        elif severity in ["WARNING", "INFO"]:
            warnings.append(structured_issue)

    return validation_status, errors, warnings


def group_errors_by_category(errors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    Group validation errors by category.

    Args:
        errors: List of error dictionaries

    Returns:
        Dictionary mapping category to list of errors
    """
    grouped = {}
    for error in errors:
        category = error.get("category", "unknown")
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(error)
    return grouped
