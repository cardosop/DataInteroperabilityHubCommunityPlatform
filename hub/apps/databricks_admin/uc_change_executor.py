"""UC DDL executor (openspec add-databricks-uc-write task 2.3).

REST-first DDL against the version-pinned UC REST surface (D2): every
supported (object type, action) combination resolves through
``API_PATHS`` — the write pins live in one place, never inline URLs.
Operations the REST surface lacks (materialized views, streaming
tables) fall back to the 0.7 SQL Statement executor with
identifier-quoted statements.

The executor operates on typed payloads — the 2.2 ``UCChangeRequest``
model embeds these same shapes when it lands (the payload vocabulary
is the contract between the request lifecycle and the executor). The
state-machine wiring (EXECUTING before / terminal after) belongs to the
2.2 lifecycle; the executor itself never touches request rows.

Failures are classified, never raw: workspace rejections propagate the
client's ``Databricks*Error`` family; the executor's OWN failures (an
unsupported combination, a missing required SQL option, a failed
statement) surface as ``UCChangeExecutionError`` with code
``DATABRICKS_DDL_EXECUTION_FAILED``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hub.apps.databricks_admin.models import UCChangeAction, UCObjectType

if TYPE_CHECKING:
    from collections.abc import Callable

    from hub.apps.databricks_admin.client import DatabricksApiClient

logger = logging.getLogger(__name__)

# UCObjectType / UCChangeAction are THE canonical vocabulary (task 2.2 —
# they live on the request model); re-exported here so executor callers
# keep importing them from this module.
__all__ = [
    "UCChangeAction",
    "UCChangeExecutionError",
    "UCChangeExecutor",
    "UCDdlPayload",
    "UCDdlResult",
    "UCObjectType",
]


@dataclass(frozen=True)
class UCDdlPayload:
    """A typed DDL request — the 2.2 request model's payload vocabulary.

    ``identifiers`` are the name parts in UC order: catalog; catalog,
    schema; catalog, schema, name. Workspace-level objects carry the
    name only.
    """

    object_type: UCObjectType
    action: UCChangeAction
    identifiers: tuple[str, ...]
    options: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.identifiers[-1]

    @property
    def full_name(self) -> str:
        return ".".join(self.identifiers)

    @property
    def catalog_name(self) -> str:
        return self.identifiers[0] if len(self.identifiers) > 1 else ""

    @property
    def schema_name(self) -> str:
        return self.identifiers[1] if len(self.identifiers) > 2 else ""


class UCChangeExecutionError(Exception):
    """The executor's own classified failure (never a workspace error —
    those keep their ``Databricks*Error`` classification)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "DATABRICKS_DDL_EXECUTION_FAILED"


@dataclass(frozen=True)
class UCDdlResult:
    terminal: str  # "EXECUTED" | "FAILED" | "SKIPPED"
    detail: str = ""


# ── REST dispatch table ──────────────────────────────────────────────────────

# (object_type, action) → (api operation, http method, body builder,
# path-params builder). Body builders take the payload and return the
# JSON body; path-params builders return the {placeholder: value} map.
_REST_PINS: dict[
    tuple[UCObjectType, UCChangeAction],
    tuple[str, str, Callable[[UCDdlPayload], dict], Callable[[UCDdlPayload], dict]],
] = {}


def _pin(payload_type: UCObjectType, action: UCChangeAction, operation: str, method: str):
    def decorator(builder):
        _REST_PINS[(payload_type, action)] = (
            operation,
            method,
            builder,
            lambda p: _path_params_for(operation, p),
        )
        return builder

    return decorator


def _path_params_for(operation: str, payload: UCDdlPayload) -> dict:
    """Only the placeholders the operation's TEMPLATE declares — the
    path() resolver rejects unexpected parameters (the 0.7 contract),
    so emitting both ``name`` and ``full_name`` for a parameter-free
    CREATE pin is an error, not a convenience."""
    import re

    from hub.apps.databricks_admin.api_paths import API_PATHS

    placeholders = set(re.findall(r"{(\w+)}", API_PATHS[operation]))
    available = {"name": payload.name, "full_name": payload.full_name}
    return {key: available[key] for key in placeholders if key in available}


def _create_body(payload: UCDdlPayload, extra: dict | None = None) -> dict:
    """The identifier-derived fields every UC CREATE body carries."""
    body: dict = {"name": payload.name}
    if payload.catalog_name:
        body["catalog_name"] = payload.catalog_name
    if payload.schema_name:
        body["schema_name"] = payload.schema_name
    for key, value in (extra or {}).items():
        if value is not None:
            body[key] = value
    for key, value in payload.options.items():
        if key in ("catalog_name", "schema_name", "name"):
            continue
        body[key] = value
    return body


def _create_table_body(payload: UCDdlPayload) -> dict:
    return _create_body(
        payload,
        {
            "table_type": payload.options.get("table_type", "MANAGED"),
            "columns": payload.options.get("columns", []),
        },
    )


@_pin(UCObjectType.CATALOG, UCChangeAction.CREATE, "uc.catalogs.create", "POST")
def _create_catalog(payload: UCDdlPayload) -> dict:
    return _create_body(payload)


@_pin(UCObjectType.CATALOG, UCChangeAction.DROP, "uc.catalogs.delete", "DELETE")
def _drop_catalog(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(UCObjectType.SCHEMA, UCChangeAction.CREATE, "uc.schemas.create", "POST")
def _create_schema(payload: UCDdlPayload) -> dict:
    return _create_body(payload)


@_pin(UCObjectType.SCHEMA, UCChangeAction.DROP, "uc.schemas.delete", "DELETE")
def _drop_schema(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(UCObjectType.TABLE, UCChangeAction.CREATE, "uc.tables.create", "POST")
def _create_table(payload: UCDdlPayload) -> dict:
    return _create_table_body(payload)


@_pin(UCObjectType.TABLE, UCChangeAction.DROP, "uc.tables.delete", "DELETE")
def _drop_table(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(UCObjectType.VIEW, UCChangeAction.CREATE, "uc.views.create", "POST")
def _create_view(payload: UCDdlPayload) -> dict:
    return _create_body(payload, {"view_definition": payload.options.get("view_definition")})


@_pin(UCObjectType.VIEW, UCChangeAction.DROP, "uc.views.delete", "DELETE")
def _drop_view(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(UCObjectType.VOLUME, UCChangeAction.CREATE, "uc.volumes.create", "POST")
def _create_volume(payload: UCDdlPayload) -> dict:
    return _create_body(payload, {"volume_type": payload.options.get("volume_type", "MANAGED")})


@_pin(UCObjectType.VOLUME, UCChangeAction.DROP, "uc.volumes.delete", "DELETE")
def _drop_volume(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(
    UCObjectType.EXTERNAL_LOCATION,
    UCChangeAction.CREATE,
    "uc.external_locations.create",
    "POST",
)
def _create_external_location(payload: UCDdlPayload) -> dict:
    return _create_body(
        payload,
        {
            "url": payload.options.get("url"),
            "credential_name": payload.options.get("credential_name"),
        },
    )


@_pin(
    UCObjectType.EXTERNAL_LOCATION,
    UCChangeAction.DROP,
    "uc.external_locations.delete",
    "DELETE",
)
def _drop_external_location(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(
    UCObjectType.STORAGE_CREDENTIAL,
    UCChangeAction.CREATE,
    "uc.storage_credentials.create",
    "POST",
)
def _create_storage_credential(payload: UCDdlPayload) -> dict:
    return _create_body(payload)


@_pin(
    UCObjectType.STORAGE_CREDENTIAL,
    UCChangeAction.DROP,
    "uc.storage_credentials.delete",
    "DELETE",
)
def _drop_storage_credential(_payload: UCDdlPayload) -> dict:
    return {}


@_pin(UCObjectType.MODEL, UCChangeAction.CREATE, "uc.models.create", "POST")
def _create_model(payload: UCDdlPayload) -> dict:
    return _create_body(payload)


@_pin(UCObjectType.MODEL, UCChangeAction.DROP, "uc.models.delete", "DELETE")
def _drop_model(_payload: UCDdlPayload) -> dict:
    return {}


# ── SQL fallback ─────────────────────────────────────────────────────────────

# Types whose DDL has NO UC REST surface — the SQL fallback builds the
# identifier-quoted statement (the 2.3 SQL-fallback contract).
_SQL_ONLY_TYPES = (UCObjectType.MATERIALIZED_VIEW, UCObjectType.STREAMING_TABLE)


def _quote(identifier: str) -> str:
    """UC identifier quoting — backticks, the UC SQL dialect."""
    return f"`{identifier.replace('`', '``')}`"


def _quote_name(payload: UCDdlPayload) -> str:
    """Quote each identifier part SEPARATELY — a three-part UC name is
    ```catalog`.`schema`.`name```, never one quoted blob (the first
    draft quoted the joined FQN as a single identifier — the executor
    pin caught it)."""
    return ".".join(_quote(part) for part in payload.identifiers)


def _sql_statement(payload: UCDdlPayload) -> str:
    if payload.object_type == UCObjectType.MATERIALIZED_VIEW:
        query = payload.options.get("query")
        if not query:
            raise UCChangeExecutionError("CREATE MATERIALIZED VIEW requires a query in options")
        return f"CREATE MATERIALIZED VIEW {_quote_name(payload)} AS {query}"
    if payload.object_type == UCObjectType.STREAMING_TABLE:
        columns = payload.options.get("columns")
        if not columns:
            raise UCChangeExecutionError(
                "CREATE STREAMING TABLE requires a columns list in options"
            )
        column_sql = ", ".join(
            f"{_quote(str(column['name']))} {column.get('type_name', 'STRING')}"
            for column in columns
        )
        return f"CREATE STREAMING TABLE {_quote_name(payload)} ({column_sql})"
    raise UCChangeExecutionError(
        f"No SQL fallback for {payload.action.value} {payload.object_type.value}"
    )


# ── executor ─────────────────────────────────────────────────────────────────


class UCChangeExecutor:
    """Executes typed UC DDL payloads — REST-first, SQL fallback.

    The CALLER owns the identity (the 2.2 lifecycle resolves the D12
    decision and builds the client); the executor never selects
    credentials and never touches request rows.

    ``tenant`` feeds the 2.4 safety guards: the denylist reads the
    ``databricks_uc_destructive_ddl_enabled`` flag from it (a missing
    tenant fails closed — destructive DDL is refused).

    ``denylist_bypass`` is the SANCTIONED 2.5 carve-out: the
    stuck-EXECUTING reaper's compensating DROP (it deletes exactly what
    a stuck CREATE request created — the rollback policy itself, not a
    user request). ANY other consumer needs design review.
    """

    def __init__(
        self,
        *,
        client: DatabricksApiClient,
        statement_executor=None,
        warehouse_id: str | None = None,
        tenant=None,
        denylist_bypass: bool = False,
    ):
        self._client = client
        self._statement_executor = statement_executor
        self._warehouse_id = warehouse_id
        self._tenant = tenant
        self._denylist_bypass = denylist_bypass

    def execute(self, payload: UCDdlPayload) -> UCDdlResult:
        # 2.4 safety layer — the denylist is the OUTERMOST guard (a
        # destructive request on a flag-off tenant is refused before
        # identifier validation and before the combination check), then
        # the execute-time identifier re-validation (identifiers can
        # never be injected past the executor), then CREATE idempotency
        # (a retried request is a no-op, not a duplicate).
        from hub.apps.databricks_admin.uc_change_guards import (
            assert_not_denylisted,
            check_exists_by_name,
            coerce_payload,
            validate_uc_identifiers,
        )

        # 2.4 review hardening: normalize the enums ONCE at the boundary
        # — the 2.2 request rows are CHARFIELDS and hand the executor
        # STRING-typed payloads; every guard, pin, and branch below sees
        # canonical enum members (unknown values are refused here).
        payload = coerce_payload(payload)
        if not self._denylist_bypass:
            assert_not_denylisted(payload, tenant=self._tenant)
        validate_uc_identifiers(payload)
        pin = _REST_PINS.get((payload.object_type, payload.action))
        if pin is not None:
            if payload.action == UCChangeAction.CREATE and check_exists_by_name(
                self._client, payload
            ):
                return UCDdlResult(
                    terminal="SKIPPED",
                    detail=(
                        f"{payload.object_type.value} {payload.full_name} already "
                        "exists by name — no-op (idempotent retry)"
                    ),
                )
            return self._execute_rest(pin, payload)
        if payload.action == UCChangeAction.CREATE and payload.object_type in _SQL_ONLY_TYPES:
            return self._execute_sql(payload)
        raise UCChangeExecutionError(
            f"Unsupported DDL combination: {payload.action.value} {payload.object_type.value}"
        )

    def _execute_rest(self, pin, payload: UCDdlPayload) -> UCDdlResult:
        operation, method, body_builder, path_params_fn = pin
        response = self._client.request(
            method,
            operation,
            path_params=path_params_fn(payload),
            json=body_builder(payload),
        )
        return UCDdlResult(terminal="EXECUTED", detail=f"{response.status_code}")

    def _execute_sql(self, payload: UCDdlPayload) -> UCDdlResult:
        from hub.apps.databricks_admin.sql_statements import (
            SqlStatementError,
            SqlStatementExecutor,
        )

        if self._statement_executor is None:
            if self._warehouse_id is None:
                raise UCChangeExecutionError(
                    "the SQL fallback requires a warehouse id or a statement executor"
                )
            self._statement_executor = SqlStatementExecutor(
                self._client, warehouse_id=self._warehouse_id
            )
        statement = _sql_statement(payload)
        try:
            result = self._statement_executor.execute(statement, self._warehouse_id)
        except SqlStatementError as exc:
            return UCDdlResult(terminal="FAILED", detail=str(exc))
        return UCDdlResult(terminal="EXECUTED", detail=result.statement_id)
