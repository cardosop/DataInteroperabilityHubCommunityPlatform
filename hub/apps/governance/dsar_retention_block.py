"""DSAR RESTRICTION cases that defer automated retention destruction (Phase 232.7)."""

from __future__ import annotations

from typing import Any

from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus

_DSAR_TERMINAL: frozenset[str] = frozenset(
    {
        DSARStatus.CLOSED_FULFILLED,
        DSARStatus.CLOSED_REJECTED,
    }
)


def _scope_matches_cell(
    cell: dict[str, Any],
    *,
    asset_id: str | None,
    dataset_id: str | None,
    file_id: str | None,
) -> bool:
    if asset_id and str(cell.get("asset_id", "")) == str(asset_id):
        return True
    if dataset_id and str(cell.get("dataset_id", "")) == str(dataset_id):
        return True
    if file_id and str(cell.get("file_id", "")) == str(file_id):
        return True

    rt = str(cell.get("resource_type") or "").upper().strip()
    rid = cell.get("resource_id")
    if rt == "ASSET" and asset_id and rid is not None and str(rid) == str(asset_id):
        return True
    if rt == "DATASET" and dataset_id and rid is not None and str(rid) == str(dataset_id):
        return True
    if rt == "FILE" and file_id and rid is not None and str(rid) == str(file_id):
        return True
    return False


def _scopes_match(scope: Any, *, asset_id, dataset_id, file_id) -> bool:
    if scope is None:
        return False
    if isinstance(scope, list):
        return any(
            _scopes_match(x, asset_id=asset_id, dataset_id=dataset_id, file_id=file_id)
            for x in scope
        )
    if isinstance(scope, dict):
        nested = scope.get("scopes")
        if isinstance(nested, list):
            return any(
                isinstance(x, dict)
                and _scope_matches_cell(
                    x, asset_id=asset_id, dataset_id=dataset_id, file_id=file_id
                )
                for x in nested
            )
        return _scope_matches_cell(scope, asset_id=asset_id, dataset_id=dataset_id, file_id=file_id)
    return False


def tenant_blocked_by_open_dsar_restriction(*, tenant_id: str) -> bool:
    """Phase 235.3 — return True if any open RESTRICTION DSAR exists for ``tenant_id``.

    The PLATFORM_ADMIN tenant-delete endpoint
    (``DELETE /api/v1/admin/tenants/{id}/``) AND the daily
    ``tenant_hard_delete_sweep`` cron both consult this helper to
    decide whether the tenant is safe to soft-delete (resp. hard-delete).
    A single open RESTRICTION-class DSAR is sufficient to block — the
    subject's restriction trumps the operator's intent to delete the
    tenant.

    "Open" = ``status NOT IN {CLOSED_FULFILLED, CLOSED_REJECTED}``,
    same convention as :func:`resource_blocked_by_open_dsar_restriction`.

    Returns
    -------
    True if at least one open RESTRICTION DSAR exists for the tenant;
    False otherwise. Tenants with NO DSARs at all return False (the
    common case on every freshly-onboarded tenant).
    """
    return (
        DSARRequest.objects.filter(
            tenant_id=tenant_id,
            request_type=DSARRequestType.RESTRICTION,
        )
        .exclude(status__in=_DSAR_TERMINAL)
        .exists()
    )


def resource_blocked_by_open_dsar_restriction(
    *,
    tenant_id: str,
    asset_id: str | None = None,
    dataset_id: str | None = None,
    file_id: str | None = None,
) -> bool:
    """
    Whether an open RESTRICTION DSAR targets ``asset_id``, ``dataset_id``, or ``file_id``.

    Conventions live under ``details_json["retention_block_scope"]``: either a mapping
    (``asset_id`` / typed ``resource_type``+``resource_id``) or a list of mappings, or a
    ``{"scopes":[...]}`` envelope.
    """
    if not any([asset_id, dataset_id, file_id]):
        return False

    qs = DSARRequest.objects.filter(
        tenant_id=tenant_id, request_type=DSARRequestType.RESTRICTION
    ).exclude(status__in=_DSAR_TERMINAL)
    for row in qs.iterator():
        payload = row.details_json if isinstance(row.details_json, dict) else {}
        scope = payload.get("retention_block_scope")
        if _scopes_match(scope, asset_id=asset_id, dataset_id=dataset_id, file_id=file_id):
            return True
    return False
