"""Phase 12 (openspec add-databricks-ml-assets task 12.2) — the ML-assets
service: registered-model versions through the MLflow REST surface +
model aliases through the UC REST (design D2/D3).

The service drives the PINNED production client (the caller owns
identity — never a second HTTP stack; the mlflow python package is a
dev-only protocol oracle at most). The P1 ``UCModel`` mirror row is the
CALLER-resolved input; on a successful operation the mirror reflects
the landed state (the version row + ``latest_version``; the model's
``aliases`` list — the P1 sync's list-of-dicts shape
``{"alias_name": ..., "version_num": ...}``).

Fail-closed: the APIs' rejections propagate the client's classified
``Databricks*Error`` family (the caller surfaces them — the
UC-DB-019 error table); a version-log whose registered model does not
exist creates it first (the GET's 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.models import (
        DatabricksMlServingEndpoint,
        UCModel,
        UCModelVersion,
    )

logger = structlog.get_logger(__name__)


class MlAssetsDisabled(Exception):
    """The D5 surface gate — the tenant's `databricks_ml_assets_enabled`
    flag is off (403 `DATABRICKS_ML_ASSETS_DISABLED`, the UC-DB-019
    error table). Raised by :func:`gate_ml_assets` BEFORE any workspace
    API call — the flag-off refusal makes ZERO network calls."""

    def __init__(self):
        super().__init__(
            "The ML-assets surface is disabled for this tenant "
            "(databricks_ml_assets_enabled is off)"
        )
        self.status_code = 403
        self.detail = {
            "code": "DATABRICKS_ML_ASSETS_DISABLED",
            "message": "The ML-assets surface is disabled for this tenant",
        }


def gate_ml_assets(view) -> None:
    """The ONE flag gate (design D5) — the 12.6 views call this in
    ``initial`` (the dlt `_gate_dlt_pipelines` pattern). A flag-off
    tenant raises :class:`MlAssetsDisabled` with ZERO API calls."""
    request = view.request
    tenant = getattr(request, "tenant", None)
    if tenant is None and hasattr(request, "user") and hasattr(request.user, "tenant"):
        tenant = request.user.tenant
    if tenant is not None and not getattr(tenant, "databricks_ml_assets_enabled", False):
        raise MlAssetsDisabled()


def _model_full_name(model: UCModel) -> str:
    """The model's UC full name — the model row's own when set, else the
    chain-derived `catalog.schema.name`."""
    full = (model.full_name or "").strip()
    if full:
        return full
    schema = model.schema
    catalog = schema.catalog
    return f"{catalog.name}.{schema.name}.{model.name}"


def _is_404(exc: Exception) -> bool:
    """The 10.3 mirror's convention — a classified not-found."""
    return getattr(exc, "status_code", None) == 404


def ensure_registered_model(client: DatabricksApiClient, full_name: str) -> dict:
    """Ensure the registered model exists through the MLflow surface —
    the GET's 404 creates it (never a blind create). Returns the API's
    reported payload (the 12.6 register view mirrors it)."""
    full_name = (full_name or "").strip()
    if not full_name:
        raise ValueError("full_name must be a non-empty string")
    try:
        response = client.request("GET", "mlflow.registered_models.get", params={"name": full_name})
    except Exception as exc:
        if not _is_404(exc):
            raise
        response = client.request(
            "POST",
            "mlflow.registered_models.create",
            json={"name": full_name},
        )
    return response.json()


def register_model_version(
    client: DatabricksApiClient,
    *,
    model: UCModel,
    source: str,
    run_id: str = "",
) -> UCModelVersion:
    """Log a model version through the MLflow surface.

    The registered model is created first when the GET reports a 404
    (never a blind create); the version-create response's payload is
    the mirror row's shape (version number, source, run id/link,
    status — as REPORTED, never invented). The model row's
    ``latest_version`` advances on success.
    """
    from hub.apps.databricks_admin.models import UCModelVersion

    full_name = _model_full_name(model)
    ensure_registered_model(client, full_name)

    response = client.request(
        "POST",
        "mlflow.model_versions.create",
        json={
            "name": full_name,
            "source": source,
            "run_id": run_id,
        },
    )
    payload = response.json()
    version_payload = payload.get("model_version") or {}
    if not isinstance(version_payload, dict):
        raise TypeError("mlflow.model_versions.create returned no model_version object")

    version_number = int(version_payload.get("version") or 0)
    if version_number <= 0:
        raise RuntimeError("mlflow.model_versions.create returned no version number")

    row = UCModelVersion.objects.create(
        model=model,
        version=version_number,
        source=str(version_payload.get("source") or source),
        run_id=str(version_payload.get("run_id") or run_id),
        run_link=str(version_payload.get("run_link") or ""),
        status=str(version_payload.get("status") or ""),
    )
    if model.latest_version < version_number:
        model.latest_version = version_number
        model.save(update_fields=["latest_version"])
    logger.info(
        "ml_model_version_registered",
        model=full_name,
        version=version_number,
    )
    return row


def _upsert_alias(model: UCModel, alias: str, version: int | None) -> None:
    """The model row's aliases list (the P1 sync's list-of-dicts shape)
    — the set replaces the entry, the remove drops it."""
    aliases = [entry for entry in model.aliases if isinstance(entry, dict)]
    aliases = [entry for entry in aliases if entry.get("alias_name") != alias]
    if version is not None:
        aliases.append({"alias_name": alias, "version_num": version})
    model.aliases = aliases
    model.save(update_fields=["aliases"])


def set_model_alias(
    client: DatabricksApiClient,
    *,
    model: UCModel,
    alias: str,
    version: int,
) -> dict[str, Any]:
    """Set (or re-point) a model alias through the UC REST surface —
    the exact journey-prose path."""
    full_name = _model_full_name(model)
    response = client.request(
        "PUT",
        "uc.model_aliases.set",
        path_params={"full_name": full_name, "alias": alias},
        json={"version_num": version},
    )
    payload = response.json()
    _upsert_alias(model, alias, version)
    logger.info("ml_model_alias_set", model=full_name, alias=alias, version=version)
    return payload


def remove_model_alias(
    client: DatabricksApiClient,
    *,
    model: UCModel,
    alias: str,
) -> None:
    """Remove a model alias through the UC REST surface."""
    full_name = _model_full_name(model)
    client.request(
        "DELETE",
        "uc.model_aliases.remove",
        path_params={"full_name": full_name, "alias": alias},
    )
    _upsert_alias(model, alias, None)
    logger.info("ml_model_alias_removed", model=full_name, alias=alias)


# ── 12.4: the flag-gated serving + Vector Search surface ─────────────────


def _mirror_endpoint(
    workspace, *, endpoint_type: str, payload: dict
) -> DatabricksMlServingEndpoint:
    """Upsert the endpoint-state mirror row from the API's payload —
    the reported state, never invented."""
    from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

    name = str(payload.get("name") or "").strip()
    if not name:
        raise TypeError("the endpoint payload has no name")
    state = payload.get("state")
    if isinstance(state, dict):
        state = state.get("ready") or state.get("config_update") or ""
    row, _ = DatabricksMlServingEndpoint.objects.update_or_create(
        workspace=workspace,
        endpoint_type=endpoint_type,
        name=name,
        defaults={
            "state": str(state or ""),
            "config": payload.get("config") or {},
        },
    )
    return row


def create_serving_endpoint(
    client: DatabricksApiClient,
    *,
    workspace,
    name: str,
    config: dict,
) -> DatabricksMlServingEndpoint:
    """Create a serving endpoint through the pinned client; the mirror
    row lands with the API's reported state."""
    response = client.request(
        "POST",
        "serving_endpoints.create",
        json={"name": name, "config": config},
    )
    return _mirror_endpoint(workspace, endpoint_type="SERVING", payload=response.json())


def list_serving_endpoints(
    client: DatabricksApiClient,
    *,
    workspace,
) -> list[dict]:
    """List the workspace's serving endpoints; the mirror upserts from
    the reported payloads (the 4.2 jobs-mirror list convention)."""
    response = client.request("GET", "serving_endpoints.list")
    payload = response.json()
    endpoints = payload.get("endpoints") or []
    if not isinstance(endpoints, list):
        raise TypeError("serving_endpoints.list returned no endpoints list")
    for endpoint in endpoints:
        if isinstance(endpoint, dict):
            _mirror_endpoint(workspace, endpoint_type="SERVING", payload=endpoint)
    return endpoints


def delete_serving_endpoint(
    client: DatabricksApiClient,
    *,
    workspace,
    name: str,
) -> None:
    """Delete a serving endpoint; the mirror row drops (the sync would
    reconcile a re-creation)."""
    client.request(
        "DELETE",
        "serving_endpoints.delete",
        path_params={"name": name},
    )
    from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

    DatabricksMlServingEndpoint.objects.filter(
        workspace=workspace, endpoint_type="SERVING", name=name
    ).delete()


def create_vector_search_endpoint(
    client: DatabricksApiClient,
    *,
    workspace,
    name: str,
    config: dict,
) -> DatabricksMlServingEndpoint:
    """Create a Vector Search endpoint through the pinned client."""
    response = client.request(
        "POST",
        "vector_search.endpoints.create",
        json={"name": name, "config": config},
    )
    return _mirror_endpoint(workspace, endpoint_type="VECTOR", payload=response.json())


# ── 12.6: the per-operation audit chokepoint (design D7) ───────────────────


def emit_ml_asset_audit(
    action: str,
    workspace,
    *,
    resource_id: str | None = None,
    actor_user=None,
    details: dict,
) -> None:
    """One audit row per PERFORMED ML-asset operation
    (resource_type=``DATABRICKS_ML_ASSET``, the D7 vocabulary). The
    mirror row's pk anchors ``resource_id`` when it exists; details
    carry identifiers only (the 3.8 convention). Emission is
    BEST-EFFORT (the Phase 273 contract) — an audit-DB outage never
    blocks the operation. A refusal emits NOTHING (the caller only
    reaches this point after the operation succeeded)."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="DATABRICKS_ML_ASSET",
            action=action,
            actor_user=actor_user,
            tenant=workspace.tenant,
            resource_id=resource_id,
            details=details,
        )
    except Exception:
        logger.warning(
            "databricks_ml_asset_audit_failed",
            extra={"action": action, "workspace_id": str(workspace.id)},
        )
