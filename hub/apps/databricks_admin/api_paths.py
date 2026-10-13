"""P0 (openspec add-databricks-control-plane task 0.5) — Databricks API path pins.

Every control-plane API call goes through this map so each endpoint's
version is pinned in ONE place. A new/upgraded endpoint = one line here,
never an inline URL in a caller.

Version conventions (per-call, Databricks REST):
- ``/api/2.0/...`` — stable GA endpoints (workspace probe, token
  management, the SQL Statement executor).
- ``/api/2.1/...`` — UC REST read/write (added in P1/P2 phases).
- ``/oidc/v1/...`` — OAuth token endpoint.

The per-call 2.0-vs-2.1 CHOICE is documented in ``API_PATH_VERSIONS``
below (task 1.8) and enforced at import by ``validate_version_pins``:
an entry without a documented version, a documented version that
disagrees with the URL, or an unversioned path fails LOUD here — never
against a live workspace.
"""

from __future__ import annotations

import re
from string import Formatter

API_PATHS: dict[str, str] = {
    "workspace.list": "/api/2.0/workspace/list",
    "oidc.token": "/oidc/v1/token",
    "sql.statements.submit": "/api/2.0/sql/statements",
    # 3.2/3.3 — SQL compute surface (add-databricks-sql-warehouses).
    "sql.warehouses.list": "/api/2.0/sql/warehouses",
    "sql.warehouses.get": "/api/2.0/sql/warehouses/{warehouse_id}",
    "sql.warehouses.create": "/api/2.0/sql/warehouses",
    "sql.warehouses.update": "/api/2.0/sql/warehouses/{warehouse_id}",
    "sql.warehouses.delete": "/api/2.0/sql/warehouses/{warehouse_id}",
    "sql.warehouses.start": "/api/2.0/sql/warehouses/{warehouse_id}/start",
    "sql.warehouses.stop": "/api/2.0/sql/warehouses/{warehouse_id}/stop",
    "sql.statements.get": "/api/2.0/sql/statements/{statement_id}",
    "sql.statements.chunk": "/api/2.0/sql/statements/{statement_id}/result/chunks/{chunk_index}",
    # UC REST reads (Phase 1) — 2.1 UC API surface.
    "uc.effective_permissions.table": "/api/2.1/unity-catalog/effective-permissions/table/{full_name}",
    # Phase 1.5 — UC estate list pins for the metadata sync fetch. All
    # 2.1 (the UC read surface per D2); query params (catalog_name,
    # schema_name, page_token, max_results) ride on the request, paths
    # stay parameter-free.
    "uc.catalogs.list": "/api/2.1/unity-catalog/catalogs",
    "uc.schemas.list": "/api/2.1/unity-catalog/schemas",
    "uc.tables.list": "/api/2.1/unity-catalog/tables",
    "uc.views.list": "/api/2.1/unity-catalog/views",
    "uc.volumes.list": "/api/2.1/unity-catalog/volumes",
    "uc.models.list": "/api/2.1/unity-catalog/models",
    "uc.external_locations.list": "/api/2.1/unity-catalog/external-locations",
    "uc.storage_credentials.list": "/api/2.1/unity-catalog/storage-credentials",
    # UC REST DDL (Phase 2.3 — the UCChangeExecutor write pins). All 2.1.
    # Parameterized delete paths carry the UC name/full_name segments.
    "uc.catalogs.create": "/api/2.1/unity-catalog/catalogs",
    "uc.catalogs.delete": "/api/2.1/unity-catalog/catalogs/{name}",
    "uc.schemas.create": "/api/2.1/unity-catalog/schemas",
    "uc.schemas.delete": "/api/2.1/unity-catalog/schemas/{full_name}",
    "uc.tables.create": "/api/2.1/unity-catalog/tables",
    "uc.tables.delete": "/api/2.1/unity-catalog/tables/{full_name}",
    "uc.views.create": "/api/2.1/unity-catalog/views",
    "uc.views.delete": "/api/2.1/unity-catalog/views/{full_name}",
    "uc.volumes.create": "/api/2.1/unity-catalog/volumes",
    "uc.volumes.delete": "/api/2.1/unity-catalog/volumes/{full_name}",
    # Phase 11 (run-transformation-on-databricks 11.4) — the managed
    # volume's file-write surface (the 11.4 staging upload).
    "fs.files.upload": "/api/2.0/fs/files/{path}",
    # Phase 12 (add-databricks-ml-assets 12.2) — the MLflow REST surface
    # (registered-model create/get + model-version create) and the UC
    # model-alias surface (the journey prose's exact PUT/DELETE paths).
    "mlflow.registered_models.create": "/api/2.0/mlflow/registered-models/create",
    "mlflow.registered_models.get": "/api/2.0/mlflow/registered-models/get",
    "mlflow.model_versions.create": "/api/2.0/mlflow/model-versions/create",
    "uc.model_aliases.set": "/api/2.1/unity-catalog/models/{full_name}/aliases/{alias}",
    "uc.model_aliases.remove": "/api/2.1/unity-catalog/models/{full_name}/aliases/{alias}",
    # Phase 12 (add-databricks-ml-assets 12.4) — the flag-gated serving +
    # Vector Search endpoint surfaces (the scoped half: create/list/delete).
    "serving_endpoints.create": "/api/2.0/serving-endpoints",
    "serving_endpoints.list": "/api/2.0/serving-endpoints",
    "serving_endpoints.delete": "/api/2.0/serving-endpoints/{name}",
    "vector_search.endpoints.create": "/api/2.0/vector-search/endpoints",
    "vector_search.endpoints.list": "/api/2.0/vector-search/endpoints",
    "vector_search.endpoints.delete": "/api/2.0/vector-search/endpoints/{name}",
    "uc.external_locations.create": "/api/2.1/unity-catalog/external-locations",
    "uc.external_locations.delete": "/api/2.1/unity-catalog/external-locations/{name}",
    "uc.storage_credentials.create": "/api/2.1/unity-catalog/storage-credentials",
    "uc.storage_credentials.delete": "/api/2.1/unity-catalog/storage-credentials/{name}",
    "uc.models.create": "/api/2.1/unity-catalog/models",
    "uc.models.delete": "/api/2.1/unity-catalog/models/{full_name}",
    # P12 (task 12.3) — the entity-tag-assignments surface (the
    # feature_store tag convention).
    "uc.tag_assignments.create": "/api/2.1/unity-catalog/entity-tag-assignments",
    "uc.tag_assignments.list": "/api/2.1/unity-catalog/entity-tag-assignments/{entity_type}/{entity_name}/tags",
    "uc.tag_assignments.delete": "/api/2.1/unity-catalog/entity-tag-assignments/{entity_type}/{entity_name}/tags/{tag_key}",
    # UC grants bridge (Phase 2.6) — the permissions read + PATCH.
    "uc.permissions.get": "/api/2.1/unity-catalog/permissions/{securable_type}/{full_name}",
    "uc.grants.patch": "/api/2.1/unity-catalog/permissions/{securable_type}/{full_name}",
    "token_management.create_pat": "/api/2.0/token-management/on-behalf-of/tokens",
    "token_management.delete": "/api/2.0/token-management/tokens/{token_id}",
    # Phase 4 — the jobs surface (add-databricks-jobs). All 2.1 (the
    # jobs API's maintained surface; D2 — REST-first via the
    # version-pinned map). 4.2 added the mirror's list pins; 4.3 the
    # client's CRUD + run-now + runs/get pins. Job/run ids ride the
    # QUERY STRING (the API's contract), so the paths stay
    # parameter-free.
    "jobs.list": "/api/2.1/jobs/list",
    "jobs.runs.list": "/api/2.1/jobs/runs/list",
    "jobs.create": "/api/2.1/jobs/create",
    "jobs.update": "/api/2.1/jobs/update",
    "jobs.delete": "/api/2.1/jobs/delete",
    "jobs.get": "/api/2.1/jobs/get",
    "jobs.run_now": "/api/2.1/jobs/run-now",
    "jobs.runs.get": "/api/2.1/jobs/runs/get",
    # Phase 8 — the account plane (add-databricks-account-plane). All 2.0
    # (the ACCOUNT API's stable GA surface on accounts.cloud.databricks.com;
    # D4 — account ops ONLY). The account id rides the path template.
    "account.metastores.create": "/api/2.0/accounts/{account_id}/metastores",
    "account.metastores.list": "/api/2.0/accounts/{account_id}/metastores",
    "account.workspaces.create": "/api/2.0/accounts/{account_id}/workspaces",
    # Phase 9 (task 9.2) — the sandbox lifecycle ops (list/delete, still
    # 2.0, still account ops ONLY).
    "account.workspaces.list": "/api/2.0/accounts/{account_id}/workspaces",
    "account.workspaces.delete": "/api/2.0/accounts/{account_id}/workspaces/{workspace_id}",
    "account.metastores.delete": "/api/2.0/accounts/{account_id}/metastores/{metastore_id}",
    # Phase 10 (add-databricks-dlt-pipelines 10.3) — the DLT pipelines
    # surface. All 2.0 (the pipelines API's maintained surface; the 9.3
    # journey drove these literal paths). Pipeline/update ids ride the
    # PATH (the API's contract); pagination/refresh params ride the
    # query string or the body.
    "pipelines.create": "/api/2.0/pipelines",
    "pipelines.list": "/api/2.0/pipelines",
    "pipelines.get": "/api/2.0/pipelines/{pipeline_id}",
    "pipelines.update": "/api/2.0/pipelines/{pipeline_id}",
    "pipelines.delete": "/api/2.0/pipelines/{pipeline_id}",
    "pipelines.updates.start": "/api/2.0/pipelines/{pipeline_id}/updates",
    "pipelines.updates.list": "/api/2.0/pipelines/{pipeline_id}/updates",
    "pipelines.updates.get": "/api/2.0/pipelines/{pipeline_id}/updates/{update_id}",
    "pipelines.stop": "/api/2.0/pipelines/{pipeline_id}/stop",
    "pipelines.events.list": "/api/2.0/pipelines/{pipeline_id}/events",
}


# Per-call version choice (task 1.8) — the documented decision behind
# every pin. The value MUST equal the version segment in ``API_PATHS``
# (``2.0`` / ``2.1`` for ``/api/<version>/...``, ``1`` for ``/oidc/v1``).
API_PATH_VERSIONS: dict[str, str] = {
    # 2.0 — the control plane's stable GA endpoints. The workspace
    # probe, token-management and the SQL Statement executor are 2.0
    # surfaces; nothing in P0/P1 upgrades them.
    "workspace.list": "2.0",
    "sql.statements.submit": "2.0",
    "sql.warehouses.list": "2.0",
    "sql.warehouses.get": "2.0",
    "sql.warehouses.create": "2.0",
    "sql.warehouses.update": "2.0",
    "sql.warehouses.delete": "2.0",
    "sql.warehouses.start": "2.0",
    "sql.warehouses.stop": "2.0",
    "sql.statements.get": "2.0",
    "sql.statements.chunk": "2.0",
    "token_management.create_pat": "2.0",
    "token_management.delete": "2.0",
    # oidc/v1 — the OAuth token endpoint (versioned as v1, not /api/2.x).
    "oidc.token": "1",
    # 2.1 — the UC REST read surface. The UC reads are pinned to 2.1
    # (the maintained UC read surface): the 2.0 unity-catalog endpoints
    # are a SUBSET without registered-models listing and without the
    # next_page_token pagination the metadata sync's fetch depends on
    # (D2 — REST-first reads via the version-pinned map).
    "uc.effective_permissions.table": "2.1",
    "uc.catalogs.list": "2.1",
    "uc.schemas.list": "2.1",
    "uc.tables.list": "2.1",
    "uc.views.list": "2.1",
    "uc.volumes.list": "2.1",
    "uc.models.list": "2.1",
    "uc.external_locations.list": "2.1",
    "uc.storage_credentials.list": "2.1",
    "uc.catalogs.create": "2.1",
    "uc.catalogs.delete": "2.1",
    "uc.schemas.create": "2.1",
    "uc.schemas.delete": "2.1",
    "uc.tables.create": "2.1",
    "uc.tables.delete": "2.1",
    "uc.views.create": "2.1",
    "uc.views.delete": "2.1",
    "uc.volumes.create": "2.1",
    "fs.files.upload": "2.0",
    "mlflow.registered_models.create": "2.0",
    "mlflow.registered_models.get": "2.0",
    "mlflow.model_versions.create": "2.0",
    "uc.model_aliases.set": "2.1",
    "uc.model_aliases.remove": "2.1",
    "serving_endpoints.create": "2.0",
    "serving_endpoints.list": "2.0",
    "serving_endpoints.delete": "2.0",
    "vector_search.endpoints.create": "2.0",
    "vector_search.endpoints.list": "2.0",
    "vector_search.endpoints.delete": "2.0",
    "uc.volumes.delete": "2.1",
    "uc.external_locations.create": "2.1",
    "uc.external_locations.delete": "2.1",
    "uc.storage_credentials.create": "2.1",
    "uc.storage_credentials.delete": "2.1",
    "uc.models.create": "2.1",
    "uc.models.delete": "2.1",
    "uc.tag_assignments.create": "2.1",
    "uc.tag_assignments.list": "2.1",
    "uc.tag_assignments.delete": "2.1",
    "uc.permissions.get": "2.1",
    "uc.grants.patch": "2.1",
    # Phase 4 — the jobs surface (2.1).
    "jobs.list": "2.1",
    "jobs.runs.list": "2.1",
    "jobs.create": "2.1",
    "jobs.update": "2.1",
    "jobs.delete": "2.1",
    "jobs.get": "2.1",
    "jobs.run_now": "2.1",
    "jobs.runs.get": "2.1",
    # Phase 8 — the account plane (2.0, the account API's GA surface).
    "account.metastores.create": "2.0",
    "account.metastores.list": "2.0",
    "account.workspaces.create": "2.0",
    # Phase 9 (task 9.2) — the sandbox lifecycle ops (2.0, same surface).
    "account.workspaces.list": "2.0",
    "account.workspaces.delete": "2.0",
    "account.metastores.delete": "2.0",
    # Phase 10 (add-databricks-dlt-pipelines 10.3) — the DLT pipelines
    # surface (2.0).
    "pipelines.create": "2.0",
    "pipelines.list": "2.0",
    "pipelines.get": "2.0",
    "pipelines.update": "2.0",
    "pipelines.delete": "2.0",
    "pipelines.updates.start": "2.0",
    "pipelines.updates.list": "2.0",
    "pipelines.updates.get": "2.0",
    "pipelines.stop": "2.0",
    "pipelines.events.list": "2.0",
}


def validate_version_pins(
    paths: dict[str, str] | None = None,
    versions: dict[str, str] | None = None,
) -> None:
    """Enforce the 1.8 version-pin contract (runs at import time).

    Every ``API_PATHS`` entry must (a) have a documented version in
    ``API_PATH_VERSIONS``, (b) actually carry a version segment in its
    URL, and (c) agree with the documented version. A violation raises
    ``RuntimeError`` at import — drift fails at development time, never
    against a live workspace.

    Parameters are injectable so tests can pin the guard's rejection
    branches without constructing broken modules.
    """
    effective_paths = paths if paths is not None else API_PATHS
    effective_versions = versions if versions is not None else API_PATH_VERSIONS

    for operation, template in effective_paths.items():
        documented = effective_versions.get(operation)
        if documented is None:
            raise RuntimeError(
                f"API path '{operation}' has no documented version pin "
                "(add it to API_PATH_VERSIONS)"
            )
        api_match = re.match(r"^/api/(\d+\.\d+)/", template)
        oidc_match = re.match(r"^/(\w+)/v(\d+)/", template)
        if api_match is None and oidc_match is None:
            raise RuntimeError(f"API path '{operation}' is not version-pinned: {template!r}")
        actual = api_match.group(1) if api_match is not None else oidc_match.group(2)
        if documented != actual:
            raise RuntimeError(
                f"API path '{operation}' is documented as {documented} "
                f"but its URL pins {actual}: {template!r}"
            )


validate_version_pins()


def path(operation: str, **params: str | int) -> str:
    """Return the version-pinned path for *operation*.

    Parameterized entries (``{statement_id}`` etc.) are formatted from
    ``**params``. Raises ValueError for unknown operations, missing path
    parameters, unformatted placeholders, AND unexpected parameters (a typo
    in a caller's ``path_params`` must fail here, not silently ship the
    wrong URL) — so callers fail at development time, not against a live
    workspace.
    """
    try:
        template = API_PATHS[operation]
    except KeyError:
        raise ValueError(
            f"Unknown Databricks API operation '{operation}'. Known operations: {sorted(API_PATHS)}"
        ) from None
    field_names = {
        field_name
        for _literal, field_name, _format_spec, _conversion in Formatter().parse(template)
        if field_name
    }
    unexpected = set(params) - field_names
    if unexpected:
        raise ValueError(
            f"Unexpected path parameter(s) {sorted(unexpected)} for operation '{operation}'"
        )
    try:
        result = template.format(**params)
    except KeyError as exc:
        raise ValueError(f"Missing path parameter {exc} for operation '{operation}'") from exc
    if "{" in result:
        raise ValueError(f"Missing path parameter(s) for operation '{operation}'")
    return result
