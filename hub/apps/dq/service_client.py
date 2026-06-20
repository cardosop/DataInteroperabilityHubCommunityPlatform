"""
DQ Service Client

Client for interacting with the dq-service microservice.

**Important Notes:**
- This client calls an EXTERNAL microservice (dq-service), not Django API endpoints
- Endpoints are microservice-specific paths (e.g., '/health', '/run')
- For Django API endpoint construction, use `hub.apps.api.utils.api_url_builder.APIURLBuilder`
- This client follows service-to-service communication patterns with circuit breaker protection

Phase 240.5.G — HMAC payload signature (defence-in-depth beyond TLS):
Every outgoing request to dq-service is signed with HMAC-SHA256 over
the wire body, keyed on ``DQ_SERVICE_INTERNAL_PAYLOAD_SECRET`` (a
distinct secret from ``INTERNAL_API_KEY``). The signature is bound
to a ``X-Internal-Payload-Timestamp`` header inside a 5-minute
window so a captured (body, sig, ts) tuple can't be replayed
later. Hub ALWAYS sends the headers regardless of whether
dq-service enforces them — the spec's rolling-deploy contract is
"Hub on day 0, dq-service flips on day 7". See
``services/shared/auth.py`` for the verifier.
"""

import hashlib
import hmac
import time
from typing import Any

import httpx
import structlog
from django.conf import settings
from django.core.cache import cache

from hub.apps.core.resilience.backoff import sleep_with_jitter
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Phase 240.5.G — payload signature constants
# ---------------------------------------------------------------------------
# Header names MUST match ``services/shared/auth.py`` verifier
# constants byte-for-byte; pinning them here as constants prevents
# a typo on either side from silently breaking signature
# verification (the wire-shape is the only spec-locked surface
# between producer + verifier).
_PAYLOAD_SIGNATURE_HEADER: str = "X-Internal-Payload-Signature"
_PAYLOAD_TIMESTAMP_HEADER: str = "X-Internal-Payload-Timestamp"


def _compute_payload_signature(body: bytes, timestamp: str, secret: str) -> str:
    """Compute HMAC-SHA256 over ``timestamp + "\\n" + body``.

    Mirrors the dq-service verifier in
    ``services/shared/auth.py:_compute_signature`` byte-for-byte.
    The timestamp is bound into the signed canonical so an
    attacker can't replay an old ``(body, sig)`` pair with a fresh
    timestamp — without it the 5-min window would be a no-op.
    """
    canonical = timestamp.encode("utf-8") + b"\n" + body
    return hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()


class DQServiceClient:
    """
    Client for interacting with the DQ service.
    """

    def __init__(self):
        # Always use the Django setting. The default matches docker-compose
        # service names; Kubernetes overrides via values.staging.yaml.
        # Previous logic tried to detect "host pytest" vs "Docker" via
        # /.dockerenv and 'unittest' in sys.modules, but this broke in
        # Kubernetes (containerd has no /.dockerenv, Django imports unittest
        # at setup time) — causing the client to connect to localhost:8083
        # instead of the real service URL on staging.
        self.base_url = getattr(settings, "DQ_SERVICE_URL", "http://dq-service:8083")
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

        # Phase 240.5.G.2 — sign the wire body with HMAC-SHA256
        # before retry-looping. Build the request explicitly via
        # ``client.build_request`` so we have the encoded body
        # bytes (multipart, JSON, urlencoded — whatever httpx
        # produces) and the signature is over what's actually
        # going on the wire. Done OUTSIDE the retry loop so a
        # retry doesn't waste CPU re-hashing the same body.
        #
        # Hub ALWAYS sends the headers, even when dq-service is
        # in soak mode (``DQ_REQUIRE_PAYLOAD_SIGNATURE=false``) —
        # this is the spec'd "rolling deploy: Hub day-0, dq-service
        # day-7" contract. Soak-mode telemetry on dq-service
        # confirms 100% of inbound requests carry the headers
        # before enforcement flips on.
        payload_secret = getattr(
            settings,
            "DQ_SERVICE_INTERNAL_PAYLOAD_SECRET",
            "",
        )
        prepared_request = self.client.build_request(
            method,
            endpoint,
            **kwargs,
        )
        if payload_secret:
            timestamp = str(int(time.time()))
            signature = _compute_payload_signature(
                body=prepared_request.content,
                timestamp=timestamp,
                secret=payload_secret,
            )
            prepared_request.headers[_PAYLOAD_TIMESTAMP_HEADER] = timestamp
            prepared_request.headers[_PAYLOAD_SIGNATURE_HEADER] = signature

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.send(prepared_request)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    logger.warning(
                        "dq_service_http_retry",
                        status_code=e.response.status_code,
                        delay=self.backoff_factor * (2**attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    # Refresh the timestamp on retry so the new
                    # request lands inside the 5-min window even if
                    # the retry backoff exhausts the original
                    # window. The signature is recomputed on the
                    # SAME body bytes (no body mutation between
                    # retries).
                    if payload_secret:
                        timestamp = str(int(time.time()))
                        signature = _compute_payload_signature(
                            body=prepared_request.content,
                            timestamp=timestamp,
                            secret=payload_secret,
                        )
                        prepared_request.headers[_PAYLOAD_TIMESTAMP_HEADER] = timestamp
                        prepared_request.headers[_PAYLOAD_SIGNATURE_HEADER] = signature
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        "dq_service_network_retry",
                        error=str(e),
                        delay=self.backoff_factor * (2**attempt),
                        attempt=attempt + 1,
                    )
                    sleep_with_jitter(attempt, self.backoff_factor)
                    if payload_secret:
                        timestamp = str(int(time.time()))
                        signature = _compute_payload_signature(
                            body=prepared_request.content,
                            timestamp=timestamp,
                            secret=payload_secret,
                        )
                        prepared_request.headers[_PAYLOAD_TIMESTAMP_HEADER] = timestamp
                        prepared_request.headers[_PAYLOAD_SIGNATURE_HEADER] = signature
                    continue
                raise
        raise Exception("Max retries exceeded for DQ service.")

    def health_check(self, timeout: float = 5.0) -> tuple[bool, str]:
        """Checks the health of the DQ service. Uses short timeout to avoid blocking when service is unreachable."""
        try:
            response = self._request_with_retry("GET", "/health", timeout=timeout)
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "dq-service")
        except Exception as e:
            # Health-check failures are expected operational events (e.g. service
            # restart, transient network partition).  WARNING, not ERROR, so that
            # test suites and monitoring don't treat them as system failures.
            logger.warning("dq_service_health_check_failed", error=str(e))
            return False, "unknown"

    def run_dq(
        self,
        file_content: bytes,
        file_format: str,
        profile_key: str = "intake_basic_gx",
        use_cache: bool = True,
        contract: Any | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
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
        # Phase 240.3.D audit-fix — resolve threshold headers ONCE up
        # front so they participate in the cache key. Without this,
        # two tenants with different ``Tenant.dq_sampling_threshold_rows``
        # values hitting the same file would share cache entries and
        # the second tenant would receive the first tenant's sampled
        # result (cross-tenant cache pollution). Resolution result is
        # also reused at request time below to avoid double-querying.
        threshold_headers = _resolve_tenant_threshold_headers(tenant_id)

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
                        custom_checks_hash = hashlib.sha256(rules_str.encode()).hexdigest()[:16]
                except Exception:
                    pass
            # Phase 240.3.D audit-fix — incorporate resolved threshold
            # values + tenant_id into the cache key. Two tenants with
            # different override settings produce different keys even
            # for the same file/profile/custom_checks. NULL-override
            # tenants share keys with the env-default population (so
            # the cache-hit ratio doesn't drop for the common case).
            threshold_key_part = (
                f"{threshold_headers.get('X-Tenant-Threshold-Bytes', '')}"
                f":{threshold_headers.get('X-Tenant-Threshold-Rows', '')}"
            )
            cache_key = (
                f"dq:run:{hashlib.sha256(file_content).hexdigest()}"
                f":{profile_key}:{custom_checks_hash}:{threshold_key_part}"
            )
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info("dq_service_cache_hit", profile_key=profile_key)
                return cached_result

        # Define fallback response
        def fallback_response(*args, **kwargs) -> dict[str, Any]:
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
        def execute_dq_check() -> dict[str, Any]:
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
            # Phase 240.3.D.3 — forward per-tenant thresholds as
            # ``X-Tenant-Threshold-*`` headers when a tenant_id is
            # supplied AND the tenant has set non-NULL overrides.
            # When either is missing, NO headers are added — dq-
            # service falls back to its env defaults
            # (``DQ_INPUT_TOO_LARGE_BYTES`` /
            # ``DQ_SAMPLING_THRESHOLD_ROWS``). This preserves
            # backwards compat with all existing run_dq callers
            # that haven't been threaded for tenant_id yet.
            #
            # Audit-fix: pass an EMPTY dict (not None) when no
            # thresholds are forwarded — ``_request_with_retry``
            # merges into ``trace_headers`` regardless, and downstream
            # introspection (test capture, OTel header extraction)
            # always sees a valid mapping. Reuses the up-front
            # resolution (cache key already incorporated above).
            request_headers: dict[str, str] = dict(threshold_headers)
            response = self._request_with_retry(
                "POST",
                "/run",
                files=files,
                data=data,
                headers=request_headers,
                timeout=run_timeout,
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
            # The circuit breaker re-raised after the fallback (or the fallback
            # was bypassed).  This is an *operational* event — the caller is
            # expected to handle it — so log at WARNING, not ERROR.
            logger.warning("dq_service_run_error", error=str(e))
            raise


# ---------------------------------------------------------------------------
# Phase 240.3.D.3 — per-tenant DQ threshold header resolution.
# ---------------------------------------------------------------------------


def _resolve_tenant_threshold_headers(tenant_id: str | None) -> dict[str, str]:
    """Resolve per-tenant DQ thresholds → ``X-Tenant-Threshold-*`` headers.

    Returns an empty dict when:
      * ``tenant_id`` is falsy / None,
      * the tenant_id doesn't resolve to a Tenant row, or
      * the tenant has both override columns NULL.

    When the tenant has either column set, the matching header is
    added. The values are bound-checked at the model layer
    (``MinValueValidator`` / ``MaxValueValidator`` on the field) so
    we don't re-validate here — a malformed value can only land via
    a direct DB write, in which case we still forward it (dq-service
    will reject in its own validator).

    Best-effort: any exception during resolution returns ``{}`` and
    the call falls through to dq-service env defaults. This keeps a
    transient DB hiccup from breaking the DQ run path.
    """
    if not tenant_id:
        return {}
    try:
        from hub.apps.tenants.models import Tenant

        tenant = (
            Tenant.objects.filter(pk=tenant_id)
            .only(
                "id",
                "dq_input_max_bytes",
                "dq_sampling_threshold_rows",
            )
            .first()
        )
        if tenant is None:
            return {}
        headers: dict[str, str] = {}
        if tenant.dq_input_max_bytes is not None:
            headers["X-Tenant-Threshold-Bytes"] = str(int(tenant.dq_input_max_bytes))
        if tenant.dq_sampling_threshold_rows is not None:
            headers["X-Tenant-Threshold-Rows"] = str(int(tenant.dq_sampling_threshold_rows))
        return headers
    except Exception as exc:
        logger.warning(
            "dq_threshold_resolve_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {}
