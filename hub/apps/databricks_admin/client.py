"""P0 (openspec add-databricks-control-plane task 0.5) — Databricks API client.

httpx-based control-plane client built ONLY on the repo's resilience stack
(no re-implementation):

- **Retries**: ``hub.apps.core.resilience.backoff.sleep_with_jitter``
  (full-jitter exponential backoff) on 429/5xx responses and transport
  errors. Client errors (400/401/403/404) are never retried.
- **Circuit breaker**: ``hub.apps.core.resilience.service_breakers``
  (shared ``CircuitBreaker``, Redis-backed with in-memory fallback) on the
  channel ``databricks_admin_{tenant_id}_{channel_key}``. 5xx responses and
  transport errors feed the breaker's failure count; an OPEN breaker fails
  fast with ``DATABRICKS_CIRCUIT_OPEN`` without touching the network.
- **Paths**: ``api_paths.py`` — every call is version-pinned through the
  operation map.
- **Credentials**: PAT bearer or OAuth M2M (real ``oidc/v1/token``
  exchange; the Redis token cache lands with task 0.6).
- **Dispatch validation**: workspace mode runs
  ``workspace.validate_for_dispatch()`` (task 0.4 DNS-rebinding guard)
  before every request.

Two construction modes:
- **workspace mode** (``workspace=``) — host + dispatch validation come
  from the ``DatabricksWorkspace`` row; the production path.
- **transport mode** (``base_url=`` or ``host=``) — a bare transport for
  tooling/tests; no dispatch validation.

Delegation mode (openspec task 1.7): pre-existing HTTP consumers — the
marketplace connector — reuse the retry/backoff/classification machinery
through ``request_path()`` with three optional seams: ``client=`` (their
own transport), ``use_breaker=False`` (the caller's circuit breaker owns
failure accounting, so the client must not double-count), and
``backoff_waiter=`` (the caller's own backoff policy). The defaults
preserve this client's original behavior exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from hub.apps.core.resilience.backoff import sleep_with_jitter
from hub.apps.core.resilience.circuit_breaker import CircuitBreakerError
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker
from hub.apps.databricks_admin.api_paths import path as api_path
from hub.apps.databricks_admin.token_cache import M2MTokenCache

if TYPE_CHECKING:
    from collections.abc import Callable

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
# Every httpx transport failure derives from RequestError (TransportError
# is a SUBCLASS), and the pre-existing marketplace connector retried the
# full RequestError family — the tuple matches that established semantics
# so the delegated path (task 1.7) keeps retrying the same errors.
_RETRYABLE_TRANSPORT_ERRORS = (httpx.RequestError,)

# Cache the token for (expires_in - margin) so a cached token is never
# served past its expiry window (spec: TTL strictly below token expiry).
_TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class DatabricksApiError(Exception):
    """Base error for all client failures (code matches the error catalogue)."""

    def __init__(
        self, message: str, *, code: str = "DATABRICKS_API_ERROR", status_code: int | None = None
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class DatabricksAuthError(DatabricksApiError):
    """401/403 — credentials rejected or forbidden."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message, code="DATABRICKS_AUTH_FAILED", status_code=status_code)


class DatabricksOBOError(DatabricksApiError):
    """OBO bearer failure (task 0b.5) — no bound token (fail-closed) or a
    refresh that failed / did not clear the 401. Interactive paths raise
    this INSTEAD of falling back to a service credential."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message, code="DATABRICKS_OBO_REFRESH_FAILED", status_code=status_code)


class DatabricksRateLimitError(DatabricksApiError):
    """429 after the retry budget is exhausted."""

    def __init__(self, message: str, *, status_code: int = 429):
        super().__init__(message, code="DATABRICKS_RATE_LIMITED", status_code=status_code)


class DatabricksUnavailableError(DatabricksApiError):
    """Circuit breaker OPEN — fail fast without a network call."""

    def __init__(self, message: str):
        super().__init__(message, code="DATABRICKS_CIRCUIT_OPEN")


class DatabricksConnectionError(DatabricksApiError):
    """Transport-level failure after retries (DNS, refused, timeout)."""

    def __init__(self, message: str):
        super().__init__(message, code="DATABRICKS_CONNECTION_ERROR")


class DatabricksServerError(DatabricksApiError):
    """5xx after the retry budget is exhausted."""

    def __init__(self, message: str, *, status_code: int):
        super().__init__(message, code="DATABRICKS_SERVER_ERROR", status_code=status_code)


class _RetryableResponse(Exception):
    """Internal signal: response status is retryable — raised INSIDE the
    breaker call so 5xx/429 responses count as breaker failures."""

    def __init__(self, response: httpx.Response):
        super().__init__(f"retryable response {response.status_code}")
        self.response = response


class DatabricksApiClient:
    """Control-plane HTTP client (see module docstring for the contract)."""

    def __init__(
        self,
        *,
        workspace=None,
        host: str | None = None,
        base_url: str | None = None,
        tenant_id: str = "",
        credential_config: dict | None = None,
        auth_mode: str = "PAT",
        token_cache: M2MTokenCache | None = None,
        obo_provider=None,
        timeout_ms: int = 30_000,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
        breaker_failure_threshold: int = 5,
        breaker_timeout_seconds: int = 60,
        client: httpx.Client | None = None,
        use_breaker: bool = True,
        backoff_waiter: Callable[[int], None] | None = None,
    ):
        self._workspace = workspace
        self._tenant_id = tenant_id
        self._credential_config = dict(credential_config or {})
        self._auth_mode = auth_mode
        # OBO mode (task 0b.5): when set, the provider supplies the
        # per-request bearer (get_bearer) and the one-shot refresh on 401
        # (refresh). Interactive paths MUST pass it; service credentials
        # are then never consulted.
        self._obo_provider = obo_provider
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        # Delegation seams (task 1.7): `client` injects the caller's own
        # transport (used verbatim — timeout_ms then does not apply);
        # `use_breaker=False` disables breaker accounting for callers that
        # wrap the call in their OWN breaker (per-attempt counting here
        # would double-count a single overall failure); `backoff_waiter`
        # replaces the jittered default with the caller's backoff policy
        # (called with the zero-indexed attempt).
        self._backoff_waiter = backoff_waiter

        if base_url is not None:
            self._base_url = base_url.rstrip("/")
            self._channel_key = base_url
        else:
            client_host = workspace.host if workspace is not None else host
            if not client_host:
                raise ValueError("DatabricksApiClient requires workspace=, host=, or base_url=")
            self._base_url = f"https://{client_host}"
            self._channel_key = str(workspace.id) if workspace is not None else client_host

        self._token_cache: M2MTokenCache = (
            token_cache if token_cache is not None else M2MTokenCache()
        )

        self._breaker = (
            get_shared_circuit_breaker(
                f"databricks_admin_{tenant_id}_{self._channel_key}",
                failure_threshold=breaker_failure_threshold,
                timeout_seconds=breaker_timeout_seconds,
            )
            if use_breaker
            else None
        )
        self._client = (
            client
            if client is not None
            else httpx.Client(base_url=self._base_url, timeout=timeout_ms / 1000.0)
        )

    # ── public API ──────────────────────────────────────────────────────

    def request(
        self,
        method: str,
        operation: str,
        *,
        path_params: dict | None = None,
        **kwargs,
    ) -> httpx.Response:
        """Perform a version-pinned API call with retries + breaker.

        ``path_params`` formats the operation's parameterized path template
        (e.g. ``statement_id``); everything else is forwarded to httpx.

        Raises the ``Databricks*Error`` family; never returns a non-2xx
        response (a 4xx/5xx is raised, not handed back).

        OBO mode (task 0b.5): a 401 on an interactive client triggers ONE
        refresh-then-retry; a second 401 (or a failed refresh, or no bound
        token) raises ``DatabricksOBOError`` (``DATABRICKS_OBO_REFRESH_FAILED``)
        — the client NEVER falls back to a service credential.
        """
        request_path = api_path(operation, **(path_params or {}))
        try:
            return self._request_with_retries(request_path, method, **kwargs)
        except DatabricksAuthError:
            if self._obo_provider is None:
                raise
            try:
                self._obo_provider.refresh()
            except DatabricksOBOError:
                raise
            except Exception as exc:
                raise DatabricksOBOError(f"OBO refresh failed: {type(exc).__name__}") from exc
            try:
                return self._request_with_retries(request_path, method, **kwargs)
            except DatabricksAuthError as exc:
                raise DatabricksOBOError("OBO token still rejected after refresh") from exc

    def request_path(self, method: str, request_path: str, **kwargs) -> httpx.Response:
        """Perform a request against a RAW API path with retries + breaker.

        The delegation seam for pre-existing HTTP consumers (openspec task
        1.7 — the marketplace connector) whose endpoints are not
        version-pinned control-plane operations: unlike ``request()`` this
        takes the literal path and skips the ``api_paths`` map and OBO
        refresh handling (service-credential paths only).

        Raises the ``Databricks*Error`` family; never returns a non-2xx
        response.
        """
        return self._request_with_retries(request_path, method, **kwargs)

    def _request_with_retries(self, request_path: str, method: str, **kwargs) -> httpx.Response:
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries):
            self._validate_dispatch()
            # Bearer resolution happens OUTSIDE the breaker: the OAuth
            # exchange's client errors (401/403) are terminal and must not
            # count as service failures, while its retryable statuses join
            # the retry loop like any other call.
            try:
                bearer = self._bearer()
            except _RetryableResponse as retryable:
                last_response = retryable.response
                if attempt == self._max_retries - 1:
                    break
                self._backoff(attempt)
                continue
            try:
                response = self._guarded_send(method, request_path, bearer=bearer, **kwargs)
            except CircuitBreakerError as exc:
                raise DatabricksUnavailableError(str(exc)) from exc
            except _RetryableResponse as retryable:
                last_response = retryable.response
                if attempt == self._max_retries - 1:
                    break
                self._backoff(attempt)
                continue
            except _RETRYABLE_TRANSPORT_ERRORS as exc:
                if attempt == self._max_retries - 1:
                    raise DatabricksConnectionError(str(exc)) from exc
                self._backoff(attempt)
                continue
            return self._raise_for_status(response)

        assert last_response is not None  # loop breaks only with a response in hand
        return self._raise_for_status(last_response)

    def test_connection(self) -> httpx.Response:
        """Probe the workspace (GET /api/2.0/workspace/list)."""
        return self.request("GET", "workspace.list")

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info) -> bool:
        self.close()
        return False

    # ── internals ───────────────────────────────────────────────────────

    def _validate_dispatch(self) -> None:
        # Task 0.4 — DNS-rebinding guard on every dispatch (workspace mode).
        if self._workspace is not None:
            self._workspace.validate_for_dispatch()

    def _guarded_send(
        self, method: str, request_path: str, *, bearer: str, **kwargs
    ) -> httpx.Response:
        # With the breaker disabled (delegation mode) the send is
        # unguarded — the CALLER's breaker wraps the whole call, so
        # per-attempt accounting here would double-count one failure.
        if self._breaker is None:
            return self._send(method, request_path, bearer=bearer, **kwargs)
        return self._breaker.call(self._send, method, request_path, bearer=bearer, **kwargs)

    def _backoff(self, attempt: int) -> None:
        # Delegation seam: an injected waiter owns the caller's backoff
        # policy; the default is the jittered exponential sleep.
        if self._backoff_waiter is not None:
            self._backoff_waiter(attempt)
            return
        sleep_with_jitter(attempt, self._retry_base_delay, self._retry_max_delay)

    def _send(self, method: str, request_path: str, *, bearer: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("Authorization", f"Bearer {bearer}")
        response = self._client.request(method, request_path, headers=headers, **kwargs)
        if response.status_code in RETRYABLE_STATUSES:
            # Raised INSIDE the breaker call so the failure counts.
            raise _RetryableResponse(response)
        return response

    def _bearer(self) -> str:
        # OBO mode: the interactive path — per-request identity from the
        # provider; service credentials are NEVER consulted here.
        if self._obo_provider is not None:
            return self._obo_provider.get_bearer()
        if self._auth_mode == "PAT":
            token = self._credential_config.get("token", "")
            if not token:
                raise DatabricksAuthError(
                    "PAT credential config has no 'token' value",
                )
            return token
        if self._auth_mode == "OAUTH_M2M":
            return self._m2m_token()
        raise ValueError(f"Unsupported auth_mode '{self._auth_mode}' (PAT|OAUTH_M2M)")

    def _m2m_token(self) -> str:
        # Task 0.6 — Redis cache around the real oidc client-credentials
        # exchange. The credential REFERENCE in the cache key is hashed by
        # M2MTokenCache; the token value itself is never logged.
        credential_ref = (
            f"{self._credential_config.get('client_id', '')}|"
            f"{self._credential_config.get('client_secret', '')}"
        )
        cached = self._token_cache.get(self._channel_key, credential_ref)
        if cached:
            return cached

        response = self._client.post(
            api_path("oidc.token"),
            data={
                "grant_type": "client_credentials",
                "scope": "all-apis",
                "client_id": self._credential_config.get("client_id", ""),
                "client_secret": self._credential_config.get("client_secret", ""),
            },
        )
        # Classify token-endpoint failures like any other call: auth errors
        # are terminal; 429/5xx are retryable and feed the breaker (raised
        # inside breaker.call via the request loop).
        if response.status_code in (401, 403):
            raise DatabricksAuthError(
                f"OAuth M2M token exchange rejected ({response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code in RETRYABLE_STATUSES:
            raise _RetryableResponse(response)
        if not 200 <= response.status_code < 300:
            raise DatabricksApiError(
                f"OAuth M2M token exchange failed with {response.status_code}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            # httpx raises json.JSONDecodeError (a ValueError) on malformed
            # bodies — surface it as a classified client error, never a raw
            # parse exception leaking through the transport layer.
            raise DatabricksApiError(
                f"OAuth M2M token response is not valid JSON: {exc}",
                status_code=response.status_code,
            ) from exc
        token = payload.get("access_token", "") if isinstance(payload, dict) else ""
        if not token:
            raise DatabricksAuthError(
                "OAuth M2M token response missing 'access_token'",
                status_code=response.status_code,
            )

        # Derive the cache TTL from the token's own lifetime (with a safety
        # margin); fall back to the cache's default capped TTL when the
        # provider omits expires_in.
        expires_in = payload.get("expires_in") if isinstance(payload, dict) else None
        if isinstance(expires_in, int) and expires_in > _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS:
            self._token_cache.set(
                self._channel_key,
                credential_ref,
                token,
                ttl_seconds=expires_in - _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS,
            )
        else:
            self._token_cache.set(self._channel_key, credential_ref, token)
        return token

    def _raise_for_status(self, response: httpx.Response) -> httpx.Response:
        if 200 <= response.status_code < 300:
            return response
        if response.status_code in (401, 403):
            raise DatabricksAuthError(
                f"Databricks rejected the request ({response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise DatabricksRateLimitError(
                "Databricks rate limit exceeded after retries",
            )
        if response.status_code >= 500:
            raise DatabricksServerError(
                f"Databricks server error ({response.status_code})",
                status_code=response.status_code,
            )
        raise DatabricksApiError(
            f"Databricks API error ({response.status_code})",
            status_code=response.status_code,
        )
