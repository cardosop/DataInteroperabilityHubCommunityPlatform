"""Phase 10 (openspec add-databricks-dlt-pipelines task 10.3) — Databricks
DLT pipelines client.

CRUD + updates (full_refresh/refresh_selection) + stop + events and the
terminal-state poll for the workspace's DLT pipelines
(``/api/2.0/pipelines`` — the pinned 2.0 pipelines surface), built on
the production ``DatabricksApiClient`` (retries, breaker,
version-pinned paths). The client owns NO credentials: the caller
constructs it with the identity-resolved client (the 3.2 mirror's
contract — "the caller owns the client").

- **Settings ship verbatim** — ``create_pipeline``/``update_pipeline``
  ship the caller's settings EXACTLY; the settings allowlist is the
  10.4 chain's gate (``databricks.dlt.create``), which runs BEFORE this
  client — the client only enforces the shape (a non-empty object).
- **Shape discipline** — wrong TYPES raise TypeError, wrong VALUES
  raise ValueError (the repo's boundary convention) BEFORE any network
  call.
- **Empty-body mutations** — the pipelines API's update/delete/stop
  answer with a legitimate empty-body 200 (the 9.2 empty-delete
  lesson): those answers are tolerated, never parsed. Reads follow the
  0.7 JSON discipline — a malformed/non-object 2xx body is a
  classified ``DatabricksApiError``.
- **The poll** — ``poll_update`` terminates ONLY on the API's terminal
  update states ({COMPLETED, FAILED, CANCELED, TIMED_OUT} — the 10.2
  vocabulary); a budget exhaustion raises the 4.4 ``_PollBudgetExhausted``
  sentinel (no new catalogue code — the 4.4 convention).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError

if TYPE_CHECKING:
    import httpx

# The terminal update vocabulary — a poll returns ONLY on these (the
# 10.2 model's reported set); everything else is still in flight.
_TERMINAL_UPDATE_STATES = frozenset({"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"})


class _PollBudgetExhausted(Exception):
    """Internal sentinel — the budget path fails the caller's operation
    (the 4.4 convention; no catalogue code for an internal budget)."""

    def __init__(self, timeout_s: float, last_state: str | None):
        super().__init__(f"poll budget exhausted after {timeout_s:.0f}s")
        self.last_state = last_state


class DatabricksPipelinesClient:
    """Databricks DLT pipelines client (see module docstring)."""

    def __init__(self, client: DatabricksApiClient):
        self._client = client

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _require_pipeline_id(pipeline_id: str) -> str:
        if not isinstance(pipeline_id, str) or not pipeline_id.strip():
            raise ValueError("pipeline_id must be a non-empty string")
        return pipeline_id.strip()

    @staticmethod
    def _require_settings(settings: dict) -> dict:
        if not isinstance(settings, dict):
            raise TypeError("settings must be a dict")
        if not settings:
            raise ValueError("settings must be a non-empty dict")
        return settings

    def _parse_json_object(self, response: httpx.Response, operation: str) -> dict:
        """The 0.7 discipline: a malformed/non-object 2xx body is a
        classified error, never a leaked JSONDecodeError."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise DatabricksApiError(
                f"{operation} returned a non-JSON body", status_code=response.status_code
            ) from exc
        if not isinstance(payload, dict):
            raise DatabricksApiError(
                f"{operation} returned a non-object body", status_code=response.status_code
            )
        return payload

    @staticmethod
    def _require_list_field(payload: dict, key: str, operation: str, status_code: int) -> list:
        reported = payload.get(key)
        if reported is None:
            return []
        if not isinstance(reported, list):
            raise DatabricksApiError(
                f"{operation} returned a non-list {key!r} field", status_code=status_code
            )
        return reported

    # ── CRUD ───────────────────────────────────────────────────────────

    def create_pipeline(self, settings: dict) -> str:
        """Create a pipeline; returns the response's pipeline id."""
        settings = self._require_settings(settings)
        response = self._client.request("POST", "pipelines.create", json=settings)
        payload = self._parse_json_object(response, "pipelines.create")
        pipeline_id = str(payload.get("pipeline_id") or "").strip()
        if not pipeline_id:
            raise DatabricksApiError(
                "pipelines.create returned no pipeline_id", status_code=response.status_code
            )
        return pipeline_id

    def list_pipelines(self) -> list[dict]:
        """List the workspace's pipelines (the ``statuses`` array)."""
        response = self._client.request("GET", "pipelines.list")
        payload = self._parse_json_object(response, "pipelines.list")
        return self._require_list_field(payload, "statuses", "pipelines.list", response.status_code)

    def get_pipeline(self, pipeline_id: str) -> dict:
        """Fetch one pipeline's payload (spec/state/name/...)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        response = self._client.request(
            "GET", "pipelines.get", path_params={"pipeline_id": pipeline_id}
        )
        return self._parse_json_object(response, "pipelines.get")

    def update_pipeline(self, pipeline_id: str, settings: dict) -> None:
        """Replace the pipeline's settings (empty-body 200 tolerated)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        settings = self._require_settings(settings)
        self._client.request(
            "PUT", "pipelines.update", path_params={"pipeline_id": pipeline_id}, json=settings
        )

    def delete_pipeline(self, pipeline_id: str) -> None:
        """Delete the pipeline (empty-body 200 tolerated)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        self._client.request("DELETE", "pipelines.delete", path_params={"pipeline_id": pipeline_id})

    # ── updates ────────────────────────────────────────────────────────

    def start_update(
        self,
        pipeline_id: str,
        *,
        full_refresh: bool = False,
        refresh_selection: dict | None = None,
    ) -> str:
        """Start an update; returns the response's update id. The
        refresh semantics ship EXACTLY as given — ``refresh_selection``
        is the API's documented object (``{tables, files}``), passed
        verbatim (the 10.5 mapping compiler constructs the selection;
        this client is the transport)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        if not isinstance(full_refresh, bool):
            raise TypeError("full_refresh must be a bool")
        if refresh_selection is not None:
            if not isinstance(refresh_selection, dict):
                raise TypeError("refresh_selection must be an object ({tables, files})")
            if not refresh_selection:
                raise ValueError("refresh_selection must be non-empty when given")
        body: dict = {"full_refresh": full_refresh}
        if refresh_selection is not None:
            body["refresh_selection"] = refresh_selection
        response = self._client.request(
            "POST",
            "pipelines.updates.start",
            path_params={"pipeline_id": pipeline_id},
            json=body,
        )
        payload = self._parse_json_object(response, "pipelines.updates.start")
        update_id = str(payload.get("update_id") or "").strip()
        if not update_id:
            raise DatabricksApiError(
                "pipelines.updates.start returned no update_id",
                status_code=response.status_code,
            )
        return update_id

    def get_update(self, pipeline_id: str, update_id: str) -> dict:
        """Fetch one update's payload (state/full_refresh/...)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        if not isinstance(update_id, str) or not update_id.strip():
            raise ValueError("update_id must be a non-empty string")
        response = self._client.request(
            "GET",
            "pipelines.updates.get",
            path_params={"pipeline_id": pipeline_id, "update_id": update_id},
        )
        return self._parse_json_object(response, "pipelines.updates.get")

    def list_updates(self, pipeline_id: str, *, page_token: str | None = None) -> list[dict]:
        """List one page of a pipeline's updates (the ``updates`` array)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        params: dict = {}
        if page_token is not None:
            if not isinstance(page_token, str) or not page_token.strip():
                raise ValueError("page_token must be a non-empty string")
            params["page_token"] = page_token
        response = self._client.request(
            "GET",
            "pipelines.updates.list",
            path_params={"pipeline_id": pipeline_id},
            params=params,
        )
        payload = self._parse_json_object(response, "pipelines.updates.list")
        return self._require_list_field(
            payload, "updates", "pipelines.updates.list", response.status_code
        )

    # ── stop / events / poll ───────────────────────────────────────────

    def stop_pipeline(self, pipeline_id: str) -> None:
        """Stop the pipeline's active update (empty-body 200 tolerated)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        self._client.request("POST", "pipelines.stop", path_params={"pipeline_id": pipeline_id})

    def list_events(self, pipeline_id: str, *, order_by: str | None = None) -> list[dict]:
        """List one page of the pipeline's events (the ``events`` array)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        params: dict = {}
        if order_by is not None:
            if not isinstance(order_by, str) or not order_by.strip():
                raise ValueError("order_by must be a non-empty string")
            params["order_by"] = order_by
        response = self._client.request(
            "GET", "pipelines.events.list", path_params={"pipeline_id": pipeline_id}, params=params
        )
        payload = self._parse_json_object(response, "pipelines.events.list")
        return self._require_list_field(
            payload, "events", "pipelines.events.list", response.status_code
        )

    def poll_update(
        self,
        pipeline_id: str,
        update_id: str,
        *,
        timeout_seconds: float = 1800.0,
        interval_seconds: float = 10.0,
    ) -> dict:
        """Poll one update to a TERMINAL state; returns the terminal
        payload. A budget exhaustion raises the 4.4 sentinel (the
        caller maps it onto its own failure path)."""
        pipeline_id = self._require_pipeline_id(pipeline_id)
        if not isinstance(update_id, str) or not update_id.strip():
            raise ValueError("update_id must be a non-empty string")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        if not isinstance(interval_seconds, (int, float)) or interval_seconds < 0:
            raise ValueError("interval_seconds must be a non-negative number")

        started = time.monotonic()
        last_state: str | None = None
        while True:
            payload = self.get_update(pipeline_id, update_id)
            state = payload.get("state")
            last_state = str(state) if state is not None else None
            if last_state in _TERMINAL_UPDATE_STATES:
                return payload
            if time.monotonic() - started > timeout_seconds:
                raise _PollBudgetExhausted(timeout_seconds, last_state)
            if interval_seconds:
                time.sleep(interval_seconds)
