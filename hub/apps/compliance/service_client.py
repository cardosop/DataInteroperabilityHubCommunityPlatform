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
from typing import Any

import httpx
import structlog
from django.conf import settings

from hub.apps.core.resilience.backoff import sleep_with_jitter
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker

logger = structlog.get_logger(__name__)


class ComplianceServiceClient:
    """
    Client for interacting with the Compliance service.

    Supports context manager protocol for deterministic connection cleanup::

        with ComplianceServiceClient() as client:
            result = client.scan_file(...)

    The underlying ``httpx.Client`` connection pool is closed on
    ``.close()`` / ``__exit__``, preventing socket leaks in long-running
    processes.
    """

    def __init__(self):
        # Always use the Django setting. The default matches docker-compose
        # service names; Kubernetes overrides via values.staging.yaml.
        # Previous logic tried to detect "host pytest" vs "Docker" via
        # /.dockerenv and 'unittest' in sys.modules, but this broke in
        # Kubernetes (containerd has no /.dockerenv, Django imports unittest
        # at setup time) — causing the client to connect to localhost:8082
        # instead of the real service URL on staging.
        self.base_url = getattr(
            settings, "COMPLIANCE_SERVICE_URL", "http://compliance-service:8082"
        )
        self.timeout = getattr(settings, "COMPLIANCE_SERVICE_TIMEOUT", 1800)  # 30 minutes default
        if not self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        # Use Django settings when available so test environments can
        # reduce retries (--no-deps means the service is unreachable
        # and every retry just adds connection-timeout + backoff delay).
        self.max_retries = getattr(settings, "COMPLIANCE_SERVICE_MAX_RETRIES", 2)
        self.backoff_factor = getattr(settings, "COMPLIANCE_SERVICE_BACKOFF_FACTOR", 1)

        self._circuit_breaker = get_shared_circuit_breaker("compliance-service")

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic. Caller headers (e.g. X-Correlation-Id) take precedence over trace headers."""
        from hub.apps.api.middleware.trace_propagation import get_trace_headers

        trace_headers = get_trace_headers() or {}

        # Add internal API key for service-to-service authentication
        internal_key = getattr(settings, "INTERNAL_API_KEY", "")
        if internal_key:
            trace_headers["X-Internal-Api-Key"] = internal_key

        caller_headers = kwargs.get("headers") or {}
        # Merge so caller headers (e.g. X-Correlation-Id) are preserved over trace/auth headers
        kwargs["headers"] = {**trace_headers, **caller_headers}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    logger.warning(
                        "compliance_service_http_retry",
                        status_code=e.response.status_code,
                        delay=self.backoff_factor * (2**attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        "compliance_service_network_retry",
                        error=str(e),
                        delay=self.backoff_factor * (2**attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    continue
                raise
        raise Exception("Max retries exceeded for Compliance service.")

    def health_check(self) -> tuple[bool, str]:
        """Checks the health of the Compliance service"""
        try:
            response = self._request_with_retry("GET", "/health")
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "compliance-service")
        except Exception as e:
            logger.warning("compliance_service_health_check_failed", error=str(e))
            return False, "unknown"

    def scan_file(
        self,
        file_content: bytes,
        file_format: str,
        scan_mode: str = "internal",
        applicable_regulations: list | None = None,
        contract: Any | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        legal_basis: str | None = None,
        legal_basis_strict: bool = False,
    ) -> dict[str, Any]:
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

        # Define fallback response (fail-closed: allowed_to_store must be
        # False when service unavailable).  v2 fields are null so callers
        # can distinguish "service returned null" from "field absent".
        def fallback_response(*args, **kwargs) -> dict[str, Any]:
            """Fallback when circuit breaker is open or service fails."""
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
                # v2 fields (19.10.6) — null on unavailability
                "cross_border_alert": None,
                "regulation_summaries": None,
                "schema_version": None,
                "error": ("Compliance service unavailable (circuit breaker open)"),
            }

        # Correlation ID for tracing (5.4.1): use provided or generate; service echoes it in response
        effective_correlation_id = correlation_id or str(uuid.uuid4())
        logger.info(
            "compliance_service_scan_file",
            correlation_id=effective_correlation_id,
            tenant_id=tenant_id or "unknown",
        )

        # Execute with circuit breaker protection
        def execute_scan() -> dict[str, Any]:
            """Execute compliance scan operation."""
            # Extract compliance policy from contract if provided (GAP-8.2.2)
            effective_regulations = applicable_regulations or []
            targeted_categories = None
            if contract:
                from hub.apps.compliance.contract_integration import (
                    ContractCompliancePolicyExtractor,
                )

                # Get jurisdictions from contract for regulatory mapping
                contract_jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(
                    contract
                )
                if contract_jurisdictions:
                    # Merge with provided regulations (contract takes precedence)
                    effective_regulations = list(
                        set(contract_jurisdictions + (applicable_regulations or []))
                    )

                # Get targeted PII categories for focused detection
                targeted_categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(
                    contract
                )

            # Prepare file for upload
            files = {"file": (f"data.{file_format}", file_content, f"application/{file_format}")}
            data = {"scan_mode": scan_mode}
            # Always pass tenant_id (5.3.2): UUID from Hub or "unknown" when absent
            data["tenant_id"] = tenant_id if tenant_id else "unknown"
            if effective_regulations:
                import json

                data["applicable_regulations"] = (
                    json.dumps(effective_regulations)
                    if isinstance(effective_regulations, list)
                    else effective_regulations
                )
            if targeted_categories:
                import json

                data["targeted_categories"] = (
                    json.dumps(targeted_categories)
                    if isinstance(targeted_categories, list)
                    else targeted_categories
                )
            if legal_basis:
                data["legal_basis"] = legal_basis

            actor_id = getattr(settings, "SERVICE_ACTOR_ID", "hub")
            req_headers = {
                "X-Correlation-Id": effective_correlation_id,
                "X-Actor-Id": actor_id,
            }
            if legal_basis_strict:
                req_headers["X-Compliance-Legal-Basis-Strict"] = "true"

            response = self._request_with_retry(
                "POST",
                "/scan-file",
                files=files,
                data=data,
                headers=req_headers,
            )
            return response.json()

        try:
            result = self._circuit_breaker.call(execute_scan, fallback=fallback_response)
            return result
        except Exception as e:
            logger.warning("compliance_service_scan_file_error", error=str(e))
            return fallback_response()

    def scan_file_async(
        self,
        file_content: bytes,
        file_format: str,
        scan_mode: str = "internal",
        applicable_regulations: list | None = None,
        legal_basis: str | None = None,
        destination_jurisdiction: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        legal_basis_strict: bool = False,
    ) -> dict[str, Any]:
        """
        POST to /scan-file-async.

        Returns the response body with ``_http_status`` injected so the
        caller can branch on 202 (async accepted) vs 200 (sync result).

        Forwards X-Actor-Id, X-Correlation-Id, X-Internal-Api-Key.

        Raises:
            httpx.HTTPStatusError: on non-200/202 HTTP errors.
            httpx.RequestError: on network-level failures.
        """
        import json as _json

        from hub.apps.api.middleware.trace_propagation import (
            get_trace_headers,
        )

        eff_cid = correlation_id or str(uuid.uuid4())
        logger.info(
            "compliance_service_scan_file_async",
            correlation_id=eff_cid,
            tenant_id=tenant_id or "unknown",
        )

        trace_hdrs = get_trace_headers() or {}
        internal_key = getattr(settings, "INTERNAL_API_KEY", "")
        if internal_key:
            trace_hdrs["X-Internal-Api-Key"] = internal_key
        actor_id = getattr(settings, "SERVICE_ACTOR_ID", "hub")
        headers = {
            **trace_hdrs,
            "X-Correlation-Id": eff_cid,
            "X-Actor-Id": actor_id,
        }
        if legal_basis_strict:
            headers["X-Compliance-Legal-Basis-Strict"] = "true"

        files = {
            "file": (
                f"data.{file_format}",
                file_content,
                f"application/{file_format}",
            )
        }
        data: dict[str, Any] = {
            "scan_mode": scan_mode,
            "tenant_id": tenant_id or "unknown",
        }
        if applicable_regulations:
            data["applicable_regulations"] = _json.dumps(applicable_regulations)
        if legal_basis:
            data["legal_basis"] = legal_basis
        if destination_jurisdiction:
            data["destination_jurisdiction"] = destination_jurisdiction

        # The async endpoint only queues the job and should respond with
        # 202 quickly.  Use a 60-second timeout — much shorter than the
        # 1 800-second timeout used for synchronous full scans — so that
        # a hanging async endpoint falls back to the sync path promptly.
        async_timeout = getattr(settings, "COMPLIANCE_ASYNC_SUBMIT_TIMEOUT", 60)

        def _fallback_async_circuit(*_a, **_kw):
            # Reuse sync path in _call_compliance_service (same as unreachable async).
            raise httpx.ConnectError("compliance-service circuit breaker open")

        def _execute_async():
            response = self.client.post(
                "/scan-file-async",
                files=files,
                data=data,
                headers=headers,
                timeout=async_timeout,
            )
            if response.status_code not in (200, 202):
                response.raise_for_status()
            result = response.json()
            result["_http_status"] = response.status_code
            return result

        return self._circuit_breaker.call(_execute_async, fallback=_fallback_async_circuit)

    def get_scan_result(self, job_id: str) -> dict[str, Any]:
        """
        GET /scan-result/{job_id} — poll for an async job result.

        Forwards X-Actor-Id, X-Correlation-Id, X-Internal-Api-Key.

        Returns:
            dict with ``"status"`` (QUEUED/RUNNING/COMPLETED/FAILED)
            and ``"result"`` payload when status is COMPLETED.

        Raises:
            httpx.HTTPStatusError / httpx.RequestError on errors.
        """
        from hub.apps.api.middleware.trace_propagation import (
            get_trace_headers,
        )

        cid = str(uuid.uuid4())
        trace_hdrs = get_trace_headers() or {}
        internal_key = getattr(settings, "INTERNAL_API_KEY", "")
        if internal_key:
            trace_hdrs["X-Internal-Api-Key"] = internal_key
        actor_id = getattr(settings, "SERVICE_ACTOR_ID", "hub")
        headers = {
            **trace_hdrs,
            "X-Correlation-Id": cid,
            "X-Actor-Id": actor_id,
        }

        def _fallback_poll_open(*_a, **_kw):
            return {"status": "QUEUED"}

        def _execute_poll():
            response = self._request_with_retry(
                "GET",
                f"/scan-result/{job_id}",
                headers=headers,
            )
            return response.json()

        return self._circuit_breaker.call(_execute_poll, fallback=_fallback_poll_open)

    # ------------------------------------------------------------------
    # Resource lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying ``httpx.Client`` connection pool.

        Safe to call multiple times — subsequent calls are no-ops.

        After ``close()`` the client instance should not be reused; create
        a new ``ComplianceServiceClient`` if further requests are needed.
        """
        if hasattr(self, "client") and self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self) -> "ComplianceServiceClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        """Last-resort cleanup guard — prefer explicit ``.close()`` or ``with``."""
        try:
            self.close()
        except Exception:
            # __del__ must not raise; the interpreter may be tearing down
            pass
