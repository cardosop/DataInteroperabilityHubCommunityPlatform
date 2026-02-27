"""
Compliance Service Client

Client for interacting with the compliance-service microservice.

**Important Notes:**
- This client calls an EXTERNAL microservice (compliance-service), not Django API endpoints
- Endpoints are microservice-specific paths (e.g., '/health', '/scan-file')
- For Django API endpoint construction, use `hub.apps.api.utils.api_url_builder.APIURLBuilder`
- This client follows service-to-service communication patterns with circuit breaker protection
- Sends X-Correlation-Id to compliance-service for request tracing (5.4.1); logs it.
"""
import uuid
import httpx
import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.conf import settings

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = logging.getLogger(__name__)


class ComplianceServiceClient:
    """
    Client for interacting with the Compliance service.
    """

    def __init__(self):
        import os
        import sys

        # Determine if we're running tests from host machine (not in Docker)
        is_in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
        is_test_env = 'pytest' in sys.modules or 'unittest' in sys.modules
        is_test_from_host = is_test_env and not is_in_docker

        # Priority: 1. Test environment from host (use localhost), 2. Settings, 3. Default
        if is_test_from_host:
            # Running tests from host machine - always use localhost
            default_url = 'http://localhost:8082'
        elif hasattr(settings, 'TESTING') and settings.TESTING:
            import os
            if os.getenv('TEST_ENVIRONMENT') == 'staging':
                default_url = 'http://localhost:8082'
            elif os.getenv('TEST_ENVIRONMENT') == 'default':
                default_url = 'http://localhost:8082'
            elif 'pytest' in sys.modules or 'unittest' in sys.modules:
                default_url = 'http://localhost:8082'
            else:
                default_url = 'http://compliance-service:8082'
        else:
            default_url = 'http://compliance-service:8082'

        # Only use settings override if not running tests from host
        if not is_test_from_host:
            self.base_url = getattr(settings, 'COMPLIANCE_SERVICE_URL', default_url)
        else:
            self.base_url = default_url
        self.timeout = getattr(settings, 'COMPLIANCE_SERVICE_TIMEOUT', 1800)  # 30 minutes default
        if not self.base_url.endswith('/'):
            self.base_url = self.base_url.rstrip('/')
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="compliance-service",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic. Caller headers (e.g. X-Correlation-Id) take precedence over trace headers."""
        from hub.apps.api.middleware.trace_propagation import get_trace_headers

        trace_headers = get_trace_headers() or {}
        caller_headers = kwargs.get('headers') or {}
        # Merge so caller headers (e.g. X-Correlation-Id) are preserved
        kwargs['headers'] = {**trace_headers, **caller_headers}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    logger.warning(
                        f"Compliance service returned {e.response.status_code}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Network error connecting to Compliance service: {e}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
        raise Exception("Max retries exceeded for Compliance service.")

    def health_check(self) -> Tuple[bool, str]:
        """Checks the health of the Compliance service"""
        try:
            response = self._request_with_retry("GET", "/health")
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "compliance-service")
        except Exception as e:
            logger.error(f"Compliance service health check failed: {e}")
            return False, "unknown"

    def scan_file(
        self,
        file_content: bytes,
        file_format: str,
        scan_mode: str = "internal",
        applicable_regulations: Optional[list] = None,
        contract: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan file for PII and compliance issues.

        Args:
            file_content: File content as bytes
            file_format: File format (csv, json, parquet)
            scan_mode: Scan mode ('internal' or 'external' for scan-only)
            applicable_regulations: Optional list of regulations to check (e.g., ['GDPR', 'HIPAA'])
            contract: Optional Contract instance to extract compliance policy from (GAP-8.2.2)
            tenant_id: Optional tenant ID for metrics/logging (5.3.2); Hub always passes this.
            correlation_id: Optional correlation ID for tracing (5.4.1); sent as X-Correlation-Id and logged.

        Returns:
            Compliance scan result dictionary
        """
        # Define fallback response (fail-closed: allowed_to_store must be False when service unavailable)
        def fallback_response(*args, **kwargs) -> Dict[str, Any]:
            """Fallback response when circuit breaker is open or service fails."""
            return {
                "overall_status": "UNKNOWN",
                "risk_level": "UNKNOWN",
                "allowed_to_store": False,
                "detected_categories": [],
                "column_findings": [],
                "regulation_mapping": {},
                "applicable_regulations": [],
                "issues": [],
                "metadata": {},
                "error": "Compliance service unavailable (circuit breaker open)",
            }

        # Correlation ID for tracing (5.4.1): use provided or generate; service echoes it in response
        effective_correlation_id = correlation_id or str(uuid.uuid4())
        logger.info(
            "Calling compliance service scan_file",
            extra={"correlation_id": effective_correlation_id, "tenant_id": tenant_id or "unknown"},
        )

        # Execute with circuit breaker protection
        def execute_scan() -> Dict[str, Any]:
            """Execute compliance scan operation."""
            # Extract compliance policy from contract if provided (GAP-8.2.2)
            effective_regulations = applicable_regulations or []
            targeted_categories = None
            if contract:
                from hub.apps.compliance.contract_integration import (
                    ContractCompliancePolicyExtractor
                )
                # Get jurisdictions from contract for regulatory mapping
                contract_jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
                if contract_jurisdictions:
                    # Merge with provided regulations (contract takes precedence)
                    effective_regulations = list(set(contract_jurisdictions + (applicable_regulations or [])))

                # Get targeted PII categories for focused detection
                targeted_categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(contract)

            # Prepare file for upload
            files = {
                'file': (f'data.{file_format}', file_content, f'application/{file_format}')
            }
            data = {
                'scan_mode': scan_mode
            }
            # Always pass tenant_id (5.3.2): UUID from Hub or "unknown" when absent
            data['tenant_id'] = tenant_id if tenant_id else "unknown"
            if effective_regulations:
                import json
                data['applicable_regulations'] = json.dumps(effective_regulations) if isinstance(effective_regulations, list) else effective_regulations
            if targeted_categories:
                import json
                data['targeted_categories'] = json.dumps(targeted_categories) if isinstance(targeted_categories, list) else targeted_categories

            response = self._request_with_retry(
                "POST",
                "/scan-file",
                files=files,
                data=data,
                headers={"X-Correlation-Id": effective_correlation_id},
            )
            return response.json()

        try:
            result = self._circuit_breaker.call(
                execute_scan,
                fallback=fallback_response
            )
            return result
        except Exception as e:
            logger.error(f"Error scanning file with Compliance service: {e}")
            return fallback_response()

