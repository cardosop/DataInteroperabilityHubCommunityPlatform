"""P12 (openspec add-databricks-ml-assets task 12.3, design D4) — the
feature-table tag convention.

A feature table is a UC table carrying the ``feature_store`` tag — the
tag is the machine-readable identity both the Hub and Databricks agree
on (no new table type, no dedicated registry). The tag set/read rides
the UC REST entity-tag-assignments surface (the Databricks-documented
2.1 family — ``POST`` create / ``GET`` list / ``DELETE`` per tag key),
and the P1 mirror's table rows annotate the tag on the next sync
(the sync's ``_normalize`` captures the tables payload's ``tags``).

Contracts:

- **The caller owns the client** (the 3.2 mirror contract) — the raw
  ``DatabricksApiClient`` is the required positional; identity
  resolution is the caller's concern.
- **The convention is exact**: the tag key is ``feature_store`` with
  the marker value ``"true"`` — the service never invents another key
  or value.
- **Fail-closed shape discipline**: a blank full_name refuses BEFORE
  any network call; a workspace rejection propagates the classified
  ``Databricks*Error``.
- **Unmark is idempotent**: a 404 on the DELETE (an already-unmarked
  table) is the goal state — never a raise.
- **The read never hangs**: the list follows the page_token chain with
  the shared repeating-token guard (a stuck token fails classified).
"""

from __future__ import annotations

from typing import Any

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError

FEATURE_STORE_TAG_KEY = "feature_store"
FEATURE_STORE_TAG_VALUE = "true"

_ENTITY_TYPE = "tables"


def _require_full_name(full_name: str) -> str:
    full_name = (full_name or "").strip()
    if not full_name:
        raise ValueError("full_name must be a non-empty string")
    return full_name


def mark_feature_table(client: DatabricksApiClient, full_name: str) -> dict:
    """Mark a UC table as a feature table (POST the tag assignment).
    Returns the assignment envelope."""
    full_name = _require_full_name(full_name)
    response = client.request(
        "POST",
        "uc.tag_assignments.create",
        json={
            "entity_type": _ENTITY_TYPE,
            "entity_name": full_name,
            "tag_key": FEATURE_STORE_TAG_KEY,
            "tag_value": FEATURE_STORE_TAG_VALUE,
        },
    )
    return response.json()


def unmark_feature_table(client: DatabricksApiClient, full_name: str) -> None:
    """Remove the feature_store tag (DELETE the assignment). An
    already-unmarked table (404) is the goal state — idempotent."""
    full_name = _require_full_name(full_name)
    try:
        client.request(
            "DELETE",
            "uc.tag_assignments.delete",
            path_params={
                "entity_type": _ENTITY_TYPE,
                "entity_name": full_name,
                "tag_key": FEATURE_STORE_TAG_KEY,
            },
        )
    except DatabricksApiError as exc:
        if getattr(exc, "status_code", None) != 404:
            raise


def table_feature_tags(client: DatabricksApiClient, full_name: str) -> list:
    """Every tag assignment on the table (the page_token chain with the
    repeating-token guard — a stuck token fails classified, never
    hangs)."""
    full_name = _require_full_name(full_name)
    items: list = []
    seen_tokens: set[str] = set()
    request_params: dict = {}
    while True:
        response = client.request(
            "GET",
            "uc.tag_assignments.list",
            path_params={"entity_type": _ENTITY_TYPE, "entity_name": full_name},
            params=request_params,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DatabricksApiError("uc.tag_assignments.list returned a non-JSON body") from exc
        if not isinstance(payload, dict):
            raise DatabricksApiError("uc.tag_assignments.list returned a non-object body")
        reported = payload.get("tag_assignments")
        if reported is None:
            return items
        if not isinstance(reported, list):
            raise DatabricksApiError("uc.tag_assignments.list returned a non-list field")
        items.extend(reported)
        next_token = payload.get("next_page_token")
        if not next_token:
            return items
        if next_token in seen_tokens:
            raise DatabricksApiError(
                f"uc.tag_assignments.list returned a repeating next_page_token "
                f"({next_token!r}) — refusing to loop the pagination"
            )
        seen_tokens.add(next_token)
        request_params["page_token"] = next_token


def is_feature_table(table_row) -> bool:
    """The derivation from the mirror row's ``tags`` annotation — a row
    whose tags carry the ``feature_store`` key is a feature table
    (never a separate registry)."""
    tags = getattr(table_row, "tags", None)
    if not isinstance(tags, list):
        return False
    return any(isinstance(tag, dict) and tag.get("key") == FEATURE_STORE_TAG_KEY for tag in tags)


def feature_tables_for_workspace(workspace) -> list[Any]:
    """The Hub-side listing: the mirror rows whose tags carry the
    feature_store key (the spec's "the Hub lists feature tables")."""
    from hub.apps.databricks_admin.models import UCTable

    rows = list(UCTable.objects.filter(schema__catalog__workspace=workspace).order_by("full_name"))
    return [row for row in rows if is_feature_table(row)]
