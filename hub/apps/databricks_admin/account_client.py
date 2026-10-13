"""P8 (openspec add-databricks-account-plane task 8.3, design D4) — the
DatabricksAccountClient.

The ACCOUNT host client: account operations ONLY — metastore create/list
and workspace create — against
``https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/...``.
Built from the shared resilience primitives (the circuit breaker +
deterministic backoff, Appendix B of the provider-boundary contract);
PAT bearer auth from the account credential. The workspace-side
``DatabricksApiClient`` is untouched — one client, one host family, one
operation vocabulary (the D4 decision).

Error classification mirrors the workspace client exactly: 401/403 →
``DatabricksAuthError`` (terminal, never retried), 429 → retried with the
jittered backoff then ``DatabricksRateLimitError``, 5xx → retried then
``DatabricksServerError``, transport failures → ``DatabricksConnectionError``,
an OPEN breaker fails fast with ``DatabricksUnavailableError`` — every
classification BEFORE any caller logic. Shape discipline BEFORE any
network call: a blank metastore/workspace name raises ValueError (the
repo's boundary convention).
"""

from __future__ import annotations

from typing import Any

import httpx

from hub.apps.core.resilience.backoff import sleep_with_jitter
from hub.apps.core.resilience.circuit_breaker import CircuitBreakerError
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker
from hub.apps.databricks_admin.api_paths import path as api_path
from hub.apps.databricks_admin.client import (
    RETRYABLE_STATUSES,
    DatabricksApiError,
    DatabricksAuthError,
    DatabricksConnectionError,
    DatabricksRateLimitError,
    DatabricksServerError,
    DatabricksUnavailableError,
    _RetryableResponse,
)

ACCOUNT_HOST = "accounts.cloud.databricks.com"
_RETRYABLE_TRANSPORT_ERRORS = (httpx.RequestError,)


class DatabricksAccountClient:
    """The account-plane API client (D4 — account operations ONLY)."""

    def __init__(
        self,
        account_id: str,
        credential_config: dict,
        *,
        base_url: str | None = None,
        timeout_ms: int = 30_000,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
        breaker_failure_threshold: int = 5,
        breaker_timeout_seconds: int = 60,
        client: httpx.Client | None = None,
        use_breaker: bool = True,
    ):
        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError("DatabricksAccountClient requires a non-blank account_id")
        self._account_id = account_id.strip()
        self._credential_config = dict(credential_config or {})
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay

        self._base_url = (base_url or f"https://{ACCOUNT_HOST}").rstrip("/")
        self._breaker = (
            get_shared_circuit_breaker(
                f"databricks_account_{self._account_id}",
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
        """Perform a version-pinned account-API call with retries + breaker.

        ``path_params`` formats the operation's parameterized path
        template (the account id); everything else is forwarded to httpx.
        Raises the ``Databricks*Error`` family; never returns a non-2xx.
        """
        request_path = api_path(operation, **(path_params or {}))
        return self._request_with_retries(request_path, method, **kwargs)

    def create_metastore(self, name: str, region: str, storage_root: str | None = None) -> dict:
        """Create a Unity Catalog metastore in the account.

        POST /api/2.0/accounts/{account_id}/metastores
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metastore name is required")
        if not isinstance(region, str) or not region.strip():
            raise ValueError("metastore region is required")
        payload: dict[str, Any] = {"name": name.strip(), "region": region.strip()}
        if storage_root:
            payload["storage_root"] = storage_root
        response = self.request(
            "POST",
            "account.metastores.create",
            path_params={"account_id": self._account_id},
            json=payload,
        )
        return self._json_body(response)

    def list_metastores(self) -> list[dict]:
        """List the account's metastores.

        GET /api/2.0/accounts/{account_id}/metastores
        """
        response = self.request(
            "GET",
            "account.metastores.list",
            path_params={"account_id": self._account_id},
        )
        payload = self._json_body(response)
        if not isinstance(payload, dict):
            raise DatabricksApiError("account metastores list response is not an object")
        return payload.get("metastores", [])

    def create_workspace(
        self,
        workspace_name: str,
        *,
        deployment_name: str | None = None,
        aws_region: str | None = None,
        pricing_tier: str | None = None,
        credentials_id: str | None = None,
        storage_configuration_id: str | None = None,
        location: str | None = None,
    ) -> dict:
        """Provision a workspace in the account.

        POST /api/2.0/accounts/{account_id}/workspaces
        """
        if not isinstance(workspace_name, str) or not workspace_name.strip():
            raise ValueError("workspace_name is required")
        payload: dict[str, Any] = {"workspace_name": workspace_name.strip()}
        for key, value in (
            ("deployment_name", deployment_name),
            ("aws_region", aws_region),
            ("pricing_tier", pricing_tier),
            ("credentials_id", credentials_id),
            ("storage_configuration_id", storage_configuration_id),
            ("location", location),
        ):
            if value:
                payload[key] = value
        response = self.request(
            "POST",
            "account.workspaces.create",
            path_params={"account_id": self._account_id},
            json=payload,
        )
        return self._json_body(response)

    def list_workspaces(self) -> list[dict]:
        """List the account's workspaces.

        GET /api/2.0/accounts/{account_id}/workspaces
        (Phase 9 task 9.2 — the sandbox destroy selector.)
        """
        response = self.request(
            "GET",
            "account.workspaces.list",
            path_params={"account_id": self._account_id},
        )
        payload = self._json_body(response)
        if not isinstance(payload, dict):
            raise DatabricksApiError("account workspaces list response is not an object")
        return payload.get("workspaces", [])

    def delete_workspace(self, workspace_id: str) -> None:
        """Permanently delete a workspace.

        DELETE /api/2.0/accounts/{account_id}/workspaces/{workspace_id}
        (Phase 9 task 9.2 — the sandbox auto-destroy.) The account API
        answers an EMPTY body on success — no JSON parse (a parse would
        misclassify a successful destroy as a transport error).
        """
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("workspace_id is required")
        response = self.request(
            "DELETE",
            "account.workspaces.delete",
            path_params={
                "account_id": self._account_id,
                "workspace_id": workspace_id.strip(),
            },
        )
        self._consume_delete_response(response)

    def delete_metastore(self, metastore_id: str) -> None:
        """Permanently delete a metastore.

        DELETE /api/2.0/accounts/{account_id}/metastores/{metastore_id}
        (Phase 9 task 9.2 — the sandbox auto-destroy's metastore sweep.)
        Same empty-body success contract as ``delete_workspace``.
        """
        if not isinstance(metastore_id, str) or not metastore_id.strip():
            raise ValueError("metastore_id is required")
        response = self.request(
            "DELETE",
            "account.metastores.delete",
            path_params={
                "account_id": self._account_id,
                "metastore_id": metastore_id.strip(),
            },
        )
        self._consume_delete_response(response)

    def _consume_delete_response(self, response: httpx.Response) -> None:
        """Delete endpoints answer empty bodies — tolerate a JSON body
        when one is present, but never REQUIRE one (the empty-200 success
        contract)."""
        if response.content:
            self._json_body(response)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info) -> bool:
        self.close()
        return False

    # ── internals (the workspace client's machinery, account-specific) ──

    def _json_body(self, response: httpx.Response):
        """Parse a 2xx body; a malformed body is a classified client
        error, never a raw parse exception leaking through the transport
        layer (the workspace client's convention)."""
        try:
            return response.json()
        except ValueError as exc:
            raise DatabricksApiError(
                f"Databricks account API response is not valid JSON: {exc}",
                status_code=response.status_code,
            ) from exc

    def _request_with_retries(self, request_path: str, method: str, **kwargs) -> httpx.Response:
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries):
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

    def _guarded_send(
        self, method: str, request_path: str, *, bearer: str, **kwargs
    ) -> httpx.Response:
        if self._breaker is None:
            return self._send(method, request_path, bearer=bearer, **kwargs)
        return self._breaker.call(self._send, method, request_path, bearer=bearer, **kwargs)

    def _backoff(self, attempt: int) -> None:
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
        # PAT-only — the account API authenticates account-console tokens.
        token = self._credential_config.get("token", "")
        if not token:
            raise DatabricksAuthError("account credential config has no 'token' value")
        return token

    def _raise_for_status(self, response: httpx.Response) -> httpx.Response:
        if 200 <= response.status_code < 300:
            return response
        if response.status_code in (401, 403):
            raise DatabricksAuthError(
                f"Databricks account API rejected the request ({response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise DatabricksRateLimitError(
                "Databricks account API rate limit exceeded after retries",
            )
        if response.status_code >= 500:
            raise DatabricksServerError(
                f"Databricks account API server error ({response.status_code})",
                status_code=response.status_code,
            )
        raise DatabricksApiError(
            f"Databricks account API error ({response.status_code})",
            status_code=response.status_code,
        )
