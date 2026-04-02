"""
DQ Service Client

Client for interacting with the dq-service microservice.

**Important Notes:**
- This client calls an EXTERNAL microservice (dq-service), not Django API endpoints
- Endpoints are microservice-specific paths (e.g., '/health', '/run')
- For Django API endpoint construction, use `hub.apps.api.utils.api_url_builder.APIURLBuilder`
- This client follows service-to-service communication patterns with circuit breaker protection
"""

import structlog
from typing import Any, Dict, Optional, Tuple

import httpx
from django.conf import settings
from django.core.cache import cache

from hub.apps.core.resilience.backoff import sleep_with_jitter
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker

logger = structlog.get_logger(__name__)


class DQServiceClient:
    """
    Client for interacting with the DQ service.
    """

    def __init__(self):
        import os
        import sys

        # Determine if we're running tests from host machine (not in Docker)
        is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
        is_test_env = "pytest" in sys.modules or "unittest" in sys.modules
        is_test_from_host = is_test_env and not is_in_docker

        # Priority: 1. Host-only pytest → localhost, 2. Django settings (so
        # @override_settings works in Docker where Compose sets DQ_SERVICE_URL),
        # 3. process env, 4. defaults by context.
        if is_test_from_host:
            default_url = "http://localhost:8083"
        else:
            env_url = os.getenv("DQ_SERVICE_URL")
            settings_url = getattr(settings, "DQ_SERVICE_URL", None)
            # Prefer Django settings during pytest/unittest so @override_settings wins over
            # process env (Docker Compose always sets DQ_SERVICE_URL).
            if is_test_env and settings_url:
                default_url = settings_url
            elif env_url:
                default_url = env_url
            elif settings_url:
                default_url = settings_url
            else:
                if is_in_docker and is_test_env:
                    import socket

                    try:
                        socket.gethostbyname("dq-service-test")
                        default_url = "http://dq-service-test:8083"
                    except socket.gaierror:
                        default_url = "http://localhost:8084"
                elif is_in_docker:
                    default_url = "http://dq-service:8083"
                else:
                    default_url = "http://dq-service:8083"

        self.base_url = default_url
        self.timeout = getattr(settings, "DQ_SERVICE_TIMEOUT", 1800)  # 30 minutes default
        if not self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1

        self._circuit_breaker = get_shared_circuit_breaker("dq-service")

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic"""
        # Add trace headers if available
        from hub.apps.api.middleware.trace_propagation import get_trace_headers

        trace_headers = get_trace_headers() or {}

        # Add internal API key for service-to-service authentication
        internal_key = getattr(settings, "INTERNAL_API_KEY", "")
        if internal_key:
            trace_headers["X-Internal-Api-Key"] = internal_key

        # Merge: caller-supplied headers take precedence over trace/auth headers
        caller_headers = kwargs.get("headers") or {}
        kwargs["headers"] = {**trace_headers, **caller_headers}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    logger.warning(
                        "dq_service_http_retry",
                        status_code=e.response.status_code,
                        delay=self.backoff_factor * (2 ** attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        "dq_service_network_retry",
                        error=str(e),
                        delay=self.backoff_factor * (2 ** attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    continue
                raise
        raise Exception("Max retries exceeded for DQ service.")

    def health_check(self, timeout: float = 5.0) -> Tuple[bool, str]:
        """Checks the health of the DQ service. Uses short timeout to avoid blocking when service is unreachable."""
        try:
            response = self._request_with_retry("GET", "/health", timeout=timeout)
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "dq-service")
        except Exception as e:
            logger.error("dq_service_health_check_failed", error=str(e))
            return False, "unknown"

    def run_dq(
        self,
        file_content: bytes,
        file_format: str,
        profile_key: str = "intake_basic_gx",
        use_cache: bool = True,
        contract: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Run DQ checks on file content.

        Args:
            file_content: File content as bytes
            file_format: File format (csv, json, parquet)
            profile_key: DQ profile key (default: intake_basic_gx)
            use_cache: Whether to use cached results
            contract: Optional Contract instance to extract quality rules from

        Returns:
            DQ result dictionary
        """
        # Check cache if enabled
        if use_cache:
            import hashlib

            custom_checks_hash = ""
            if contract:
                try:
                    from hub.apps.dq.contract_integration import (
                        ContractQualityRulesExtractor,
                    )
                    rules = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
                    if rules:
                        import json as _json
                        rules_str = _json.dumps(
                            [str(r) for r in rules if r is not None],
                            sort_keys=True,
                        )
                        custom_checks_hash = hashlib.sha256(
                            rules_str.encode()
                        ).hexdigest()[:16]
                except Exception:
                    pass
            cache_key = (
                f"dq:run:{hashlib.sha256(file_content).hexdigest()}"
                f":{profile_key}:{custom_checks_hash}"
            )
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info("dq_service_cache_hit", profile_key=profile_key)
                return cached_result

        # Define fallback response
        def fallback_response(*args, **kwargs) -> Dict[str, Any]:
            """Fallback response when circuit breaker is open or service fails."""
            return {
                "overall_status": "UNKNOWN",
                "quality_score": 0.0,
                "checks": [],
                "engine_type": "UNKNOWN",
                "engine_version": "unknown",
                "profile_key": profile_key,
                "metadata": {"error": "DQ service unavailable (circuit breaker open)"},
            }

        # Execute with circuit breaker protection
        def execute_dq_check() -> Dict[str, Any]:
            """Execute DQ check operation."""
            # Extract quality rules from contract if provided (GAP-8.2.1)
            custom_checks = None
            effective_profile_key = profile_key
            if contract:
                from hub.apps.dq.contract_integration import ContractQualityRulesExtractor

                # Get contract profile key if specified
                effective_profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
                    contract, fallback=profile_key
                )
                # Get contract quality checks
                custom_checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)

            # Prepare file for upload
            files = {"file": (f"data.{file_format}", file_content, f"application/{file_format}")}
            data = {"profile_key": effective_profile_key}

            # Add custom checks if available (will be passed to DQ service as JSON string)
            if custom_checks:
                # Convert DQCheck objects to serializable format
                custom_checks_list = [
                    {
                        "check_id": check.check_id,
                        "name": check.name,
                        "category": check.category.value,
                        "severity": check.severity.value,
                        "expectation_type": check.expectation_type,
                        "params": check.params,
                        "target_level": check.target_level,
                        "target_column": check.target_column,
                        "target_pattern": check.target_pattern,
                    }
                    for check in custom_checks
                ]
                import json

                data["custom_checks"] = json.dumps(custom_checks_list)

            run_timeout = getattr(settings, "DQ_RUN_TIMEOUT", 120)
            response = self._request_with_retry(
                "POST", "/run", files=files, data=data, timeout=run_timeout
            )
            result = response.json()

            # Cache result if enabled
            if use_cache:
                cache.set(cache_key, result, timeout=getattr(settings, "DQ_RESULT_CACHE_TTL", 3600))

            return result

        try:
            result = self._circuit_breaker.call(execute_dq_check, fallback=fallback_response)
            return result
        except Exception as e:
            # If circuit breaker raised an exception (not caught by fallback),
            # re-raise it to allow callers to handle it
            # This allows tests to verify error handling behavior
            logger.error("dq_service_run_error", error=str(e))
            # Re-raise the exception to allow callers to handle it
            # The circuit breaker will have already called the fallback if appropriate
            raise
