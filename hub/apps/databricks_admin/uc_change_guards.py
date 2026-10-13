"""UC DDL safety guards (openspec add-databricks-uc-write task 2.4) — D3.

Three structural, fail-closed guards on every UC change:

1. DENYLIST — the destructive family ((type, DROP) for every securable)
   requires the ``databricks_uc_destructive_ddl_enabled`` tenant flag
   (DRAFT, default-off). The denylist is the OUTERMOST guard: it fires
   BEFORE identifier validation and BEFORE the unsupported-combination
   check, with ZERO network calls. A missing/unknown tenant fails closed
   (the flag resolves to False). Future securables auto-join the family
   until explicitly excluded via ``_NON_DESTRUCTIVE_DROPS`` — the
   escape hatch is the DENYLIST, never a permissive default.

2. IDENTIFIER REGEX — a UC identifier pattern per securable level
   (catalog/schema/table/view/volume/model/alias; the SQL-only types
   reuse the table pattern). ``validate_uc_identifier`` is the
   request-time API (the 2.2 lifecycle consumes it);
   ``validate_uc_identifiers`` re-validates the whole payload and is
   ALSO wired into ``UCChangeExecutor.execute`` — identifiers can never
   be injected past the executor.

3. IDEMPOTENCY — ``check_exists_by_name`` asks the workspace's pinned
   LIST surface (parent-scoped) whether the payload's name already
   exists; the executor turns a present name into a no-op SKIPPED
   result BEFORE any mutation call. SQL-only types (materialized
   views/streaming tables) have no UC REST list surface — the check
   returns False and the workspace's own duplicate rejection applies
   (documented limitation).

All rejections are ``UCDdlSafetyError`` with a machine-readable code
(``DATABRICKS_DDL_DENYLISTED`` / ``DATABRICKS_DDL_INVALID_IDENTIFIER``)
and ZERO network calls — safety failures never touch the workspace.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hub.apps.databricks_admin.models import UCChangeAction, UCObjectType
from hub.apps.databricks_admin.uc_change_executor import UCDdlPayload

if TYPE_CHECKING:
    from collections.abc import Callable

    from hub.apps.databricks_admin.client import DatabricksApiClient


class UCDdlSafetyError(Exception):
    """A fail-closed safety rejection (denylist / identifier regex)."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def coerce_payload(payload: UCDdlPayload) -> UCDdlPayload:
    """Normalize the payload's enums to CANONICAL members.

    The 2.2 ``UCChangeRequest`` model persists ``object_type``/``action``
    as CHARFIELDS, so the lifecycle hands the executor STRING-typed
    payloads ("CATALOG"/"DROP"). TextChoices members compare equal to
    their strings, so dict/pin lookups tolerate the raw shape — but the
    denylist's error construction and the SQL-only branch dereference
    ``.value``, and an UNKNOWN value key-errors. An unclassifiable
    request is REFUSED here (fail-closed: never executed, zero network).
    """
    try:
        object_type = UCObjectType(payload.object_type)
        action = UCChangeAction(payload.action)
    except ValueError as exc:
        raise UCDdlSafetyError(
            f"unknown UC change enum: {exc} — denied (fail-closed)",
            code="DATABRICKS_DDL_DENYLISTED",
        ) from exc
    if object_type is payload.object_type and action is payload.action:
        return payload
    return UCDdlPayload(
        object_type=object_type,
        action=action,
        identifiers=payload.identifiers,
        options=payload.options,
    )


# ── 1. denylist ──────────────────────────────────────────────────────────────

# Every DROP is destructive by default — future securables join the
# family automatically (fail-closed) until explicitly excluded here.
_NON_DESTRUCTIVE_DROPS: frozenset[tuple[UCObjectType, UCChangeAction]] = frozenset()

DESTRUCTIVE_PATTERNS: frozenset[tuple[UCObjectType, UCChangeAction]] = (
    frozenset({(object_type, UCChangeAction.DROP) for object_type in UCObjectType})
    - _NON_DESTRUCTIVE_DROPS
)


def assert_not_denylisted(payload: UCDdlPayload, *, tenant=None) -> None:
    """The OUTERMOST guard: refuse destructive DDL when the tenant flag
    is off (or the tenant is unknown — fail closed). ZERO network."""
    payload = coerce_payload(payload)
    if (payload.object_type, payload.action) not in DESTRUCTIVE_PATTERNS:
        return
    enabled = bool(getattr(tenant, "databricks_uc_destructive_ddl_enabled", False))
    if not enabled:
        raise UCDdlSafetyError(
            f"{payload.action.value} {payload.object_type.value} is destructive and "
            "flag-gated (databricks_uc_destructive_ddl_enabled is off for this tenant)",
            code="DATABRICKS_DDL_DENYLISTED",
        )


# ── 2. identifier regex ──────────────────────────────────────────────────────

# UC identifier rules: 1-255 chars, leading letter/underscore, then
# letters/digits/underscores. Model ALIASES additionally allow hyphens
# (Databricks's alias charset).
_BASE_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]{0,254}"

UC_IDENTIFIER_PATTERNS: dict[str, re.Pattern] = {
    level: re.compile(rf"^{_BASE_IDENTIFIER}$")
    for level in (
        "catalog",
        "schema",
        "table",
        "view",
        "volume",
        "model",
        "materialized_view",
        "streaming_table",
        "external_location",
        "storage_credential",
    )
}
UC_IDENTIFIER_PATTERNS["alias"] = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,254}$")

# Securable → the identifier levels its name parts must satisfy, in UC
# order (catalog; catalog, schema; catalog, schema, name — workspace-level
# objects carry the name only).
_LEVELS_BY_TYPE: dict[UCObjectType, tuple[str, ...]] = {
    UCObjectType.CATALOG: ("catalog",),
    UCObjectType.SCHEMA: ("catalog", "schema"),
    UCObjectType.TABLE: ("catalog", "schema", "table"),
    UCObjectType.VIEW: ("catalog", "schema", "view"),
    UCObjectType.MATERIALIZED_VIEW: ("catalog", "schema", "materialized_view"),
    UCObjectType.STREAMING_TABLE: ("catalog", "schema", "streaming_table"),
    UCObjectType.VOLUME: ("catalog", "schema", "volume"),
    UCObjectType.MODEL: ("catalog", "schema", "model"),
    UCObjectType.EXTERNAL_LOCATION: ("external_location",),
    UCObjectType.STORAGE_CREDENTIAL: ("storage_credential",),
}


def validate_uc_identifier(level: str, value: str) -> None:
    """The request-time identifier check (the 2.2 lifecycle's API)."""
    pattern = UC_IDENTIFIER_PATTERNS.get(level)
    if pattern is None:
        raise UCDdlSafetyError(
            f"unknown identifier level {level!r}",
            code="DATABRICKS_DDL_INVALID_IDENTIFIER",
        )
    if not isinstance(value, str):
        raise UCDdlSafetyError(
            f"identifier part for level {level} must be a string, got {type(value).__name__}",
            code="DATABRICKS_DDL_INVALID_IDENTIFIER",
        )
    if not pattern.fullmatch(value):
        raise UCDdlSafetyError(
            f"invalid UC identifier {value!r} for level {level} (expected {pattern.pattern})",
            code="DATABRICKS_DDL_INVALID_IDENTIFIER",
        )


def validate_uc_identifiers(payload: UCDdlPayload) -> None:
    """Validate the payload's whole identifier chain (arity + per-part
    regex). Wired into the executor — the execute-time re-validation."""
    payload = coerce_payload(payload)
    levels = _LEVELS_BY_TYPE[payload.object_type]
    if len(payload.identifiers) != len(levels):
        raise UCDdlSafetyError(
            f"{payload.object_type.value} takes {len(levels)} identifier part(s), "
            f"got {len(payload.identifiers)} ({payload.identifiers!r})",
            code="DATABRICKS_DDL_INVALID_IDENTIFIER",
        )
    for level, part in zip(levels, payload.identifiers, strict=True):
        validate_uc_identifier(level, part)


# ── 3. idempotency — existence-check-by-name before CREATE ───────────────────

# Securable → (pinned list operation, response list key, parent-params
# builder). The parent scope mirrors the estate fetch (1.5): schemas are
# listed per catalog, schema-scoped objects per catalog+schema.
_LIST_SURFACES: dict[UCObjectType, tuple[str, str, Callable[[UCDdlPayload], dict]]] = {
    UCObjectType.CATALOG: ("uc.catalogs.list", "catalogs", lambda _p: {}),
    UCObjectType.SCHEMA: (
        "uc.schemas.list",
        "schemas",
        lambda p: {"catalog_name": p.catalog_name},
    ),
    UCObjectType.TABLE: (
        "uc.tables.list",
        "tables",
        lambda p: {"catalog_name": p.catalog_name, "schema_name": p.schema_name},
    ),
    UCObjectType.VIEW: (
        "uc.views.list",
        "views",
        lambda p: {"catalog_name": p.catalog_name, "schema_name": p.schema_name},
    ),
    UCObjectType.VOLUME: (
        "uc.volumes.list",
        "volumes",
        lambda p: {"catalog_name": p.catalog_name, "schema_name": p.schema_name},
    ),
    UCObjectType.MODEL: (
        "uc.models.list",
        "models",
        lambda p: {"catalog_name": p.catalog_name, "schema_name": p.schema_name},
    ),
    UCObjectType.EXTERNAL_LOCATION: (
        "uc.external_locations.list",
        "external_locations",
        lambda _p: {},
    ),
    UCObjectType.STORAGE_CREDENTIAL: (
        "uc.storage_credentials.list",
        "storage_credentials",
        lambda _p: {},
    ),
}


def check_exists_by_name(client: DatabricksApiClient, payload: UCDdlPayload) -> bool:
    """One pinned parent-scoped LIST call — does the name already exist?

    SQL-only types have no UC REST list surface: False (the workspace's
    own duplicate rejection applies — documented limitation). Non-dict
    rows in a workspace answer are junk: they simply do not match (an
    unprovable existence never crashes the check)."""
    payload = coerce_payload(payload)
    entry = _LIST_SURFACES.get(payload.object_type)
    if entry is None:
        return False
    operation, list_key, params_fn = entry
    from hub.apps.databricks_admin.uc_sync import _json_object

    params = dict(params_fn(payload))
    params["max_results"] = 100
    body = _json_object(client, operation, params)
    rows = body.get(list_key) or []
    return any(isinstance(row, dict) and row.get("name") == payload.name for row in rows)
