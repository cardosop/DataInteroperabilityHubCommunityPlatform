"""P0 (openspec add-databricks-control-plane task 0.7) — SQL statement executor.

Thin, real client over the Databricks SQL Statement Execution API
(``POST /api/2.0/sql/statements``), built on ``DatabricksApiClient``:

- **submit** — POST the statement with warehouse id and ``wait_timeout``;
  returns the ``statement_id``.
- **poll** — GET the statement; states ``PENDING/RUNNING/QUEUED`` are
  in-flight, ``SUCCEEDED/FAILED/CANCELED/CLOSED`` are terminal.
- **chunk pagination** — ``execute()`` follows ``result.next_chunk_internal``
  through the pinned chunk endpoint until no further chunk is signalled.
- **statement timeouts** — the ``wait_timeout`` hint is passed to the API;
  the client-side ``poll_timeout_seconds`` budget raises
  ``SqlStatementTimeoutError`` (``DATABRICKS_STATEMENT_TIMEOUT``) when the
  statement never reaches a terminal state.
- **warehouse-id resolution** — ``resolve_warehouse_id`` accepts a bare
  warehouse id or the ``/sql/1.0/warehouses/<id>`` path form (from a
  connection ``http_path``).

The executor performs NO logging of SQL bodies (PII risk — the Phase 273
contract requires hash-only logging for SPARQL and the same discipline
applies here).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import cast

import httpx

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError

_TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"})

DEFAULT_WAIT_TIMEOUT = "10s"


class SqlStatementError(DatabricksApiError):
    """Terminal FAILED statement — carries the Databricks error message."""

    def __init__(self, message: str, *, code: str = "DATABRICKS_STATEMENT_FAILED"):
        super().__init__(message, code=code)


class SqlStatementTimeoutError(DatabricksApiError):
    """Statement never reached a terminal state within the poll budget."""

    def __init__(self, statement_id: str, elapsed_seconds: float):
        super().__init__(
            f"Statement '{statement_id}' did not reach a terminal state "
            f"within {elapsed_seconds:.1f}s",
            code="DATABRICKS_STATEMENT_TIMEOUT",
        )


@dataclass
class SqlStatementResult:
    """Terminal result of an executed statement."""

    statement_id: str
    state: str
    rows: list[list] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0


class SqlStatementExecutor:
    """SQL Statement Execution API executor (see module docstring)."""

    def __init__(
        self,
        client: DatabricksApiClient,
        warehouse_id: str | None = None,
        poll_interval_seconds: float = 0.5,
        poll_timeout_seconds: float = 300.0,
    ):
        self._client = client
        self._warehouse_id = warehouse_id
        self._poll_interval = poll_interval_seconds
        self._poll_timeout = poll_timeout_seconds
        # Plain client for external (presigned) chunk URLs — no bearer auth.
        self._external_client = httpx.Client(timeout=30.0)

    # ── warehouse-id resolution ─────────────────────────────────────────

    @staticmethod
    def resolve_warehouse_id(value: str) -> str:
        """Resolve a warehouse id from a bare id or an http_path form.

        ``/sql/1.0/warehouses/abc`` and ``https://host/sql/1.0/warehouses/abc``
        both resolve to ``abc``.
        """
        resolved = value.strip()
        if not resolved:
            raise ValueError("warehouse id must not be empty")
        marker = "/sql/1.0/warehouses/"
        if marker in resolved:
            resolved = resolved.split(marker, 1)[1].split("/", 1)[0]
        if not resolved:
            raise ValueError("warehouse id must not be empty")
        return resolved

    # ── API operations ──────────────────────────────────────────────────

    def submit(
        self,
        statement: str,
        warehouse_id: str | None = None,
        wait_timeout: str = DEFAULT_WAIT_TIMEOUT,
    ) -> str:
        """Submit a statement; returns the statement_id."""
        statement_id, _payload = self._submit_payload(statement, warehouse_id, wait_timeout)
        return statement_id

    def _submit_payload(
        self,
        statement: str,
        warehouse_id: str | None,
        wait_timeout: str,
        parameters: dict | None = None,
    ) -> tuple[str, dict]:
        """Submit and return (statement_id, full response payload).

        The submit response can already carry the terminal state AND the
        first result chunk when ``wait_timeout`` covers the execution —
        ``execute()`` must not discard it. ``parameters`` rides the
        statement API's named-parameter channel (7.3 — the cost-sync
        delta bound; the values never ride in the SQL text).
        """
        payload: dict = {"statement": statement, "wait_timeout": wait_timeout}
        if parameters:
            payload["parameters"] = parameters
        resolved_warehouse = (
            self.resolve_warehouse_id(warehouse_id) if warehouse_id else self._warehouse_id
        )
        if resolved_warehouse:
            payload["warehouse_id"] = self.resolve_warehouse_id(resolved_warehouse)
        response = self._client.request("POST", "sql.statements.submit", json=payload)
        body = self._parse_json(response)
        # Phase 9 (task 9.4 contract pin) — a 2xx body WITHOUT a
        # statement_id must be a CLASSIFIED client error, never a raw
        # KeyError (a retry can land a 200 whose shape the API changed —
        # the executor's contract is classification, not dict indexing).
        statement_id = body.get("statement_id") if isinstance(body, dict) else None
        if not isinstance(statement_id, str) or not statement_id:
            raise DatabricksApiError(
                "SQL Statement API response carries no statement_id",
                status_code=response.status_code,
            )
        return statement_id, body

    def get(self, statement_id: str) -> dict:
        """Poll the statement's current state."""
        response = self._client.request(
            "GET", "sql.statements.get", path_params={"statement_id": statement_id}
        )
        return self._parse_json(response)

    def fetch_chunk(self, statement_id: str, chunk_index: int) -> dict:
        """Fetch one result chunk through the pinned chunk endpoint."""
        response = self._client.request(
            "GET",
            "sql.statements.chunk",
            path_params={"statement_id": statement_id, "chunk_index": chunk_index},
        )
        return self._parse_json(response)

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict:
        """Classified JSON parsing — a malformed 2xx body must surface as a
        client error, never a raw JSONDecodeError through the transport."""
        try:
            return cast("dict", response.json())
        except ValueError as exc:
            raise DatabricksApiError(
                f"SQL Statement API returned invalid JSON: {exc}",
                status_code=response.status_code,
            ) from exc

    def execute(
        self,
        statement: str,
        warehouse_id: str | None = None,
        wait_timeout: str = DEFAULT_WAIT_TIMEOUT,
        parameters: dict | None = None,
    ) -> SqlStatementResult:
        """Submit → poll to a terminal state → collect all chunks.

        The submit response itself is the FIRST result carrier (the API
        returns the terminal state + first chunk inline when ``wait_timeout``
        covers execution), so polling starts from it instead of discarding
        it. A non-terminal state (or an anomalous missing state) keeps
        polling until the REAL time budget expires — timeout takes priority
        over state anomalies. ``parameters`` rides the named-parameter
        channel (7.3).
        """
        statement_id, payload = self._submit_payload(
            statement, warehouse_id, wait_timeout, parameters
        )

        started = time.monotonic()
        while payload.get("status", {}).get("state", "") not in _TERMINAL_STATES:
            if time.monotonic() - started > self._poll_timeout:
                raise SqlStatementTimeoutError(statement_id, time.monotonic() - started)
            time.sleep(self._poll_interval)
            payload = self.get(statement_id)

        state = payload.get("status", {}).get("state", "")

        if state == "FAILED":
            message = payload.get("status", {}).get("error", {}).get("message", "unknown error")
            raise SqlStatementError(f"Statement '{statement_id}' failed: {message}")
        if state == "CANCELED":
            raise SqlStatementError(
                f"Statement '{statement_id}' was canceled",
                code="DATABRICKS_STATEMENT_CANCELED",
            )
        # CLOSED with a result is treated like SUCCEEDED; CLOSED WITHOUT one
        # is an anomalous terminal state and must never masquerade as an
        # empty success.
        if state == "CLOSED" and not payload.get("result"):
            raise SqlStatementError(
                f"Statement '{statement_id}' closed without a result",
            )

        rows, columns = self._collect_rows(statement_id, payload)
        row_count = payload.get("result", {}).get("row_count", len(rows))
        return SqlStatementResult(
            statement_id=statement_id,
            state=state,
            rows=rows,
            columns=columns,
            row_count=row_count,
        )

    def _collect_rows(
        self, statement_id: str, initial_payload: dict
    ) -> tuple[list[list], list[str]]:
        """Collect data_array rows across internal chunks (pagination)."""
        manifest = initial_payload.get("manifest", {})
        columns = [col.get("name", "") for col in manifest.get("schema", {}).get("columns", [])]

        rows: list[list] = []
        payload = initial_payload
        seen_chunks: set[int] = set()
        hops = 0
        max_hops = 1000  # safety bound against a misbehaving chunk loop

        while payload is not None and hops < max_hops:
            hops += 1
            result = payload.get("result", {})
            chunk_index = int(result.get("chunk_index", 0))

            chunk_rows = result.get("data_array", []) or []
            rows.extend(chunk_rows)

            next_chunk = result.get("next_chunk_internal")
            if next_chunk:
                # next_chunk_internal carries the row_offset; the pinned
                # chunk endpoint returns the NEXT chunk from that offset.
                # Loop detection applies ONLY to internal hops — external
                # chunk payloads legitimately repeat chunk_index 0.
                next_index = chunk_index + 1
                if next_index in seen_chunks:
                    raise SqlStatementError(
                        f"Statement '{statement_id}' signalled chunk {next_index} twice — "
                        "pagination loop detected",
                    )
                seen_chunks.add(next_index)
                payload = self.fetch_chunk(statement_id, next_index)
                continue

            # Large results are delivered through external_links (presigned
            # cloud URLs): each entry's next_chunk_internal_link points at
            # the following chunk; follow it once per hop.
            external = result.get("external_links") or []
            next_external = next(
                (entry for entry in external if entry.get("next_chunk_internal_link")),
                None,
            )
            if next_external:
                payload = self._fetch_external_chunk(
                    statement_id, next_external["next_chunk_internal_link"]
                )
                continue
            break

        return rows, columns

    def _fetch_external_chunk(self, statement_id: str, link: str) -> dict:
        """Fetch one external (presigned) result chunk.

        The link comes from the Databricks payload (https presigned URLs in
        production). Scheme abuse is still blocked: only http(s) is allowed,
        never file:// etc.; the fetch never goes through the bearer client.
        """
        if not link.startswith(("https://", "http://")):
            raise SqlStatementError(
                f"Statement '{statement_id}' returned a non-http(s) external chunk link",
            )
        response = self._external_client.get(link)
        if not 200 <= response.status_code < 300:
            raise DatabricksApiError(
                f"External chunk fetch failed with {response.status_code}",
                status_code=response.status_code,
            )
        return self._parse_json(response)
