"""Phase 3 (openspec add-databricks-sql-warehouses task 3.3) — SQL
warehouse compute client.

CRUD + start/stop for the workspace's SQL warehouses
(``/api/2.0/sql/warehouses`` — the pinned 2.0 SQL compute surface),
built on the production ``DatabricksApiClient`` (retries, breaker,
version-pinned paths). The client owns NO credentials: the caller
constructs it with the identity-resolved client (the 3.2 mirror's
contract — "the caller owns the client").

- **list/get/create/update/delete** — the CRUD surface. ``serverless``
  and ``auto_stop_mins`` are first-class payload fields (never
  string-munged options); a classic create carries the size tier
  instead, and a serverless+size contradiction is a ValueError BEFORE
  any network call (the mirror invariant: serverless rows carry NULL
  size).
- **start/stop** — idempotent-state aware (the spec scenario): the
  client fetches the warehouse's current state first; START on
  STARTING/RUNNING and STOP on STOPPING/STOPPED/DELETING are no-op
  successes (``None``). A performed call returns the endpoint's
  payload (``{}`` for the API's empty-body answer — mutation answers
  are parsed leniently; a READ body is parsed strictly, the 0.7 JSON
  discipline).
- **Errors** — workspace rejections propagate the classified
  ``Databricks*Error`` family; the Hub's OWN state failures (a missing
  or unknown reported state, START on a DELETING warehouse) raise
  ``DatabricksWarehouseStateError`` (``DATABRICKS_WAREHOUSE_STATE_ERROR``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError
from hub.apps.databricks_admin.models import DatabricksSqlWarehouseState

if TYPE_CHECKING:
    import httpx

# The idempotency sets mirror DatabricksSqlWarehouseState (3.2) — the
# single source of truth for the compute state vocabulary.
_START_NOOP_STATES = frozenset({"STARTING", "RUNNING"})
_STOP_NOOP_STATES = frozenset({"STOPPING", "STOPPED", "DELETING"})


class DatabricksWarehouseStateError(DatabricksApiError):
    """The Hub's own state failure — the client cannot reason about the
    warehouse's lifecycle state (missing/unknown reported state, or an
    action impossible in the current state)."""

    def __init__(self, message: str):
        super().__init__(message, code="DATABRICKS_WAREHOUSE_STATE_ERROR")


class DatabricksComputeClient:
    """SQL warehouse compute client (see module docstring)."""

    def __init__(self, client: DatabricksApiClient):
        self._client = client

    # ── reads ───────────────────────────────────────────────────────────

    def list(self) -> list[dict]:
        """List the workspace's SQL warehouses (the ``warehouses`` array)."""
        response = self._client.request("GET", "sql.warehouses.list")
        payload = self._parse_json_object(response, "sql.warehouses.list")
        warehouses = payload.get("warehouses")
        if not isinstance(warehouses, list):
            raise DatabricksApiError(
                "sql.warehouses.list returned a non-list 'warehouses' field",
                status_code=response.status_code,
            )
        return warehouses

    def get(self, warehouse_id: str) -> dict:
        """Fetch one warehouse's payload (id/state/name/serverless/...)."""
        warehouse_id = self._require_warehouse_id(warehouse_id)
        response = self._client.request(
            "GET", "sql.warehouses.get", path_params={"warehouse_id": warehouse_id}
        )
        return self._parse_json_object(response, "sql.warehouses.get")

    # ── mutations ───────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: str,
        serverless: bool,
        auto_stop_mins: int,
        size: str | None = None,
    ) -> str:
        """Create a SQL warehouse; returns the response's warehouse id.

        ``serverless`` and ``auto_stop_mins`` ship EXACTLY as given (the
        spec scenario); a classic create requires the size tier, a
        serverless one forbids it. Shape violations raise TypeError
        (wrong type) / ValueError (wrong value or combination) BEFORE
        any network call.
        """
        payload = self._build_create_payload(name, serverless, auto_stop_mins, size)
        response = self._client.request("POST", "sql.warehouses.create", json=payload)
        body = self._parse_json_object(response, "sql.warehouses.create")
        warehouse_id = str(body.get("id") or "").strip()
        if not warehouse_id:
            raise DatabricksApiError(
                "sql.warehouses.create returned no warehouse id",
                status_code=response.status_code,
            )
        return warehouse_id

    def update(
        self,
        warehouse_id: str,
        *,
        name: str | None = None,
        serverless: bool | None = None,
        auto_stop_mins: int | None = None,
        size: str | None = None,
    ) -> dict:
        """PATCH the warehouse — only the given fields ship."""
        warehouse_id = self._require_warehouse_id(warehouse_id)
        payload = self._build_update_payload(name, serverless, auto_stop_mins, size)
        response = self._client.request(
            "PATCH",
            "sql.warehouses.update",
            path_params={"warehouse_id": warehouse_id},
            json=payload,
        )
        return self._parse_mutation_json(response, "sql.warehouses.update")

    def delete(self, warehouse_id: str) -> None:
        """Delete the warehouse (the API answers without a body)."""
        warehouse_id = self._require_warehouse_id(warehouse_id)
        self._client.request(
            "DELETE", "sql.warehouses.delete", path_params={"warehouse_id": warehouse_id}
        )

    # ── lifecycle ───────────────────────────────────────────────────────

    def start(self, warehouse_id: str) -> dict | None:
        """START the warehouse; a no-op success (``None``) when it is
        already STARTING/RUNNING. START on a DELETING warehouse raises
        ``DatabricksWarehouseStateError`` (no START is issued)."""
        warehouse_id = self._require_warehouse_id(warehouse_id)
        state = self._current_state(warehouse_id, action="start")
        if state in _START_NOOP_STATES:
            return None
        if state == "DELETING":
            raise DatabricksWarehouseStateError(
                f"Warehouse '{warehouse_id}' is DELETING — it cannot be started"
            )
        return self._lifecycle_post("sql.warehouses.start", warehouse_id)

    def stop(self, warehouse_id: str) -> dict | None:
        """STOP the warehouse; a no-op success (``None``) when it is
        already STOPPING/STOPPED/DELETING — the desired end state is
        reached or already being reached."""
        warehouse_id = self._require_warehouse_id(warehouse_id)
        state = self._current_state(warehouse_id, action="stop")
        if state in _STOP_NOOP_STATES:
            return None
        return self._lifecycle_post("sql.warehouses.stop", warehouse_id)

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _require_warehouse_id(warehouse_id: str) -> str:
        """An empty id would format into ``/api/2.0/sql/warehouses/`` —
        a silently wrong URL. Fail at development time instead (the 0.7
        resolve_warehouse_id discipline)."""
        warehouse_id = warehouse_id.strip()
        if not warehouse_id:
            raise ValueError("warehouse id must not be empty")
        return warehouse_id

    def _current_state(self, warehouse_id: str, *, action: str) -> str:
        """The warehouse's reported state, or the classified state error.

        A missing state or a state OUTSIDE the 3.2 vocabulary makes the
        idempotency decision impossible — the Hub's own failure, raised
        as ``DATABRICKS_WAREHOUSE_STATE_ERROR`` before any mutation.
        """
        payload = self.get(warehouse_id)
        raw_state = payload.get("state")
        state = str(raw_state) if raw_state else ""
        if not state:
            raise DatabricksWarehouseStateError(
                f"Warehouse '{warehouse_id}' reported no state — "
                f"cannot decide the {action} idempotency"
            )
        if state not in DatabricksSqlWarehouseState.values:
            raise DatabricksWarehouseStateError(
                f"Warehouse '{warehouse_id}' reported unknown state '{state}' — "
                f"cannot decide the {action} idempotency"
            )
        return state

    def _lifecycle_post(self, operation: str, warehouse_id: str) -> dict:
        response = self._client.request(
            "POST", operation, path_params={"warehouse_id": warehouse_id}
        )
        return self._parse_mutation_json(response, operation)

    @staticmethod
    def _build_create_payload(
        name: str, serverless: bool, auto_stop_mins: int, size: str | None
    ) -> dict:
        """The create envelope: serverless + auto-stop ship exactly; a
        classic create carries the size tier. Wrong TYPES raise
        TypeError, wrong VALUES/combinations raise ValueError (the
        repo's boundary convention) — always BEFORE any network call."""
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if not name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(serverless, bool):
            raise TypeError("serverless must be a bool")
        if not isinstance(auto_stop_mins, int) or isinstance(auto_stop_mins, bool):
            raise TypeError("auto_stop_mins must be an integer of minutes")
        if auto_stop_mins < 1:
            raise ValueError("auto_stop_mins must be a positive integer of minutes")
        payload = {"name": name, "serverless": serverless, "auto_stop_mins": auto_stop_mins}
        if serverless:
            if size is not None:
                raise ValueError("a serverless warehouse has no size tier (size must be None)")
        else:
            # None = the required size is MISSING (a value problem);
            # a non-string = a wrong TYPE; a blank string = a value
            # problem again.
            if size is None:
                raise ValueError("a classic warehouse requires a size tier")
            if not isinstance(size, str):
                raise TypeError("size must be a string")
            if not size.strip():
                raise ValueError("a classic warehouse requires a size tier")
            payload["size"] = size
        return payload

    @staticmethod
    def _build_update_payload(
        name: str | None,
        serverless: bool | None,
        auto_stop_mins: int | None,
        size: str | None,
    ) -> dict:
        payload: dict = {}
        if name is not None:
            if not isinstance(name, str):
                raise TypeError("name must be a string")
            if not name.strip():
                raise ValueError("name must be a non-empty string")
            payload["name"] = name
        if serverless is not None:
            if not isinstance(serverless, bool):
                raise TypeError("serverless must be a bool")
            payload["serverless"] = serverless
        if auto_stop_mins is not None:
            if not isinstance(auto_stop_mins, int) or isinstance(auto_stop_mins, bool):
                raise TypeError("auto_stop_mins must be an integer of minutes")
            if auto_stop_mins < 1:
                raise ValueError("auto_stop_mins must be a positive integer of minutes")
            payload["auto_stop_mins"] = auto_stop_mins
        if size is not None:
            if not isinstance(size, str):
                raise TypeError("size must be a string")
            if not size.strip():
                raise ValueError("size must be a non-empty string")
            payload["size"] = size
        if serverless is True and size is not None:
            raise ValueError("a serverless warehouse has no size tier (size must be None)")
        if not payload:
            raise ValueError("update requires at least one of name/serverless/auto_stop_mins/size")
        return payload

    @staticmethod
    def _parse_json_object(response: httpx.Response, operation: str) -> dict:
        """Strict object parse for READ/create answers — a malformed or
        non-object 2xx body is a classified client error, never a leaked
        JSONDecodeError (the 0.7 discipline)."""
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
    def _parse_mutation_json(response: httpx.Response, operation: str) -> dict:
        """Lenient object parse for mutation answers: the compute API's
        PATCH/start/stop may legitimately answer 200 with an EMPTY body —
        that is a successful call (``{}``), never a parse crash."""
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise DatabricksApiError(
                f"{operation} returned a non-JSON body", status_code=response.status_code
            ) from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise DatabricksApiError(
                f"{operation} returned a non-object body", status_code=response.status_code
            )
        return payload
