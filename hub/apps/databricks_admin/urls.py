"""URL routing for the Databricks control plane (workspaces, credentials, …)."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from hub.apps.databricks_admin.sso_views import DatabricksSSOViewSet
from hub.apps.databricks_admin.views import CredentialViewSet, WorkspaceViewSet

router = DefaultRouter()
router.register(r"workspaces", WorkspaceViewSet, basename="databricks-workspace")
router.register(r"sso", DatabricksSSOViewSet, basename="databricks-sso")

from hub.apps.databricks_admin.account_estate_views import AccountEstateViewSet
from hub.apps.databricks_admin.account_views import AccountProvisioningViewSet
from hub.apps.databricks_admin.dlt_views import DatabricksDltPipelineViewSet
from hub.apps.databricks_admin.ml_asset_views import DatabricksMlAssetViewSet

router.register(r"accounts", AccountProvisioningViewSet, basename="databricks-account")
router.register(r"estate-summary", AccountEstateViewSet, basename="databricks-account-estate")

urlpatterns = router.urls

from hub.apps.databricks_admin.job_views import DatabricksJobViewSet
from hub.apps.databricks_admin.sql_warehouse_views import SqlWarehouseViewSet
from hub.apps.databricks_admin.uc_views import UCBrowseViewSet

# Nested credential endpoints (manual mapping — DRF DefaultRouter has no
# nested-prefix support without an extra dependency).
urlpatterns += [
    path(
        "workspaces/<uuid:workspace_id>/credentials/",
        CredentialViewSet.as_view({"get": "list", "post": "create"}),
        name="databricks-credential-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/credentials/<uuid:pk>/rotate/",
        CredentialViewSet.as_view({"post": "rotate"}),
        name="databricks-credential-rotate",
    ),
]

# UC browse endpoints (task 1.3) — nested under the workspace registry.
# The path params are uuid-style ids; the ViewSet actions re-validate the
# tenant chain (the URL converter is routing sugar, not the security
# boundary — RLS + the tenant-scoped lookups are).
# SQL-warehouse lifecycle endpoints (task 3.7) — nested under the
# workspace registry. warehouse_id is the Databricks-side id (not a
# UUID); the ViewSet re-validates the tenant chain (URL converters are
# routing sugar — RLS + tenant-scoped lookups are the boundary).
urlpatterns += [
    # DLT pipeline management (task 10.7) — the page + the CLI ride
    # this ONE surface (design D7). The pipeline_id is the
    # Databricks-side id (a str); the ViewSet re-validates the tenant
    # chain (URL converters are routing sugar — RLS + tenant-scoped
    # lookups are the boundary).
    path(
        "workspaces/<uuid:workspace_id>/dlt-pipelines/",
        DatabricksDltPipelineViewSet.as_view({"get": "list", "post": "create"}),
        name="dlt-pipeline-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/dlt-pipelines/<str:pipeline_id>/start/",
        DatabricksDltPipelineViewSet.as_view({"post": "start"}),
        name="dlt-pipeline-start",
    ),
    path(
        "workspaces/<uuid:workspace_id>/dlt-pipelines/<str:pipeline_id>/",
        DatabricksDltPipelineViewSet.as_view({"put": "update", "delete": "destroy"}),
        name="dlt-pipeline-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/dlt-pipelines/<str:pipeline_id>/stop/",
        DatabricksDltPipelineViewSet.as_view({"post": "stop"}),
        name="dlt-pipeline-stop",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/models/",
        DatabricksMlAssetViewSet.as_view({"get": "models", "post": "register_model"}),
        name="ml-asset-models",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/models/<uuid:model_id>/versions/",
        DatabricksMlAssetViewSet.as_view({"post": "log_version"}),
        name="ml-asset-model-versions",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/models/<uuid:model_id>/aliases/<str:alias>/",
        DatabricksMlAssetViewSet.as_view({"put": "set_alias", "delete": "remove_alias"}),
        name="ml-asset-model-alias",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/feature-tables/",
        DatabricksMlAssetViewSet.as_view({"get": "feature_tables"}),
        name="ml-asset-feature-tables",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/tables/<uuid:table_id>/feature-tag/",
        DatabricksMlAssetViewSet.as_view(
            {"post": "mark_feature_table", "delete": "unmark_feature_table"}
        ),
        name="ml-asset-feature-tag",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/serving-endpoints/",
        DatabricksMlAssetViewSet.as_view(
            {"get": "serving_endpoints", "post": "create_serving_endpoint"}
        ),
        name="ml-asset-serving-endpoints",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/serving-endpoints/<str:name>/",
        DatabricksMlAssetViewSet.as_view({"delete": "delete_serving_endpoint"}),
        name="ml-asset-serving-endpoint-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/ml-assets/vector-search-endpoints/",
        DatabricksMlAssetViewSet.as_view(
            {"get": "vector_search_endpoints", "post": "create_vector_search_endpoint"}
        ),
        name="ml-asset-vector-search-endpoints",
    ),
    path(
        "workspaces/<uuid:workspace_id>/sql-warehouses/",
        SqlWarehouseViewSet.as_view({"get": "list"}),
        name="databricks-sql-warehouse-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/sql-warehouses/<str:warehouse_id>/start/",
        SqlWarehouseViewSet.as_view({"post": "start"}),
        name="databricks-sql-warehouse-start",
    ),
    path(
        "workspaces/<uuid:workspace_id>/sql-warehouses/<str:warehouse_id>/stop/",
        SqlWarehouseViewSet.as_view({"post": "stop"}),
        name="databricks-sql-warehouse-stop",
    ),
    # Job-fleet reads (task 4.5) — nested under the workspace registry.
    # job_id is the Databricks-side id (not a UUID); the ViewSet
    # re-validates the tenant chain (URL converters are routing sugar —
    # RLS + tenant-scoped lookups are the boundary).
    path(
        "workspaces/<uuid:workspace_id>/jobs/",
        DatabricksJobViewSet.as_view({"get": "list"}),
        name="databricks-job-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/jobs/<str:job_id>/runs/",
        DatabricksJobViewSet.as_view({"get": "runs"}),
        name="databricks-job-run-list",
    ),
]

urlpatterns += [
    path(
        "workspaces/<uuid:workspace_id>/uc/catalogs/",
        UCBrowseViewSet.as_view({"get": "catalogs"}),
        name="databricks-uc-catalogs",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/catalogs/<uuid:catalog_id>/schemas/",
        UCBrowseViewSet.as_view({"get": "schemas"}),
        name="databricks-uc-schemas",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/schemas/<uuid:schema_id>/tables/",
        UCBrowseViewSet.as_view({"get": "tables"}),
        name="databricks-uc-tables",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/schemas/<uuid:schema_id>/views/",
        UCBrowseViewSet.as_view({"get": "views"}),
        name="databricks-uc-views",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/schemas/<uuid:schema_id>/volumes/",
        UCBrowseViewSet.as_view({"get": "volumes"}),
        name="databricks-uc-volumes",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/schemas/<uuid:schema_id>/models/",
        UCBrowseViewSet.as_view({"get": "models"}),
        name="databricks-uc-models",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/tables/<uuid:table_id>/",
        UCBrowseViewSet.as_view({"get": "table_detail"}),
        name="databricks-uc-table-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/external-locations/",
        UCBrowseViewSet.as_view({"get": "external_locations"}),
        name="databricks-uc-external-locations",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/storage-credentials/",
        UCBrowseViewSet.as_view({"get": "storage_credentials"}),
        name="databricks-uc-storage-credentials",
    ),
]

# UC change-request endpoints (task 2.8 — U4 approval UX) nested under
# the workspace registry + the cross-workspace approver inbox.
from hub.apps.databricks_admin.uc_change_views import (
    UCApprovalInboxViewSet,
    UCChangeRequestViewSet,
)

urlpatterns += [
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/",
        UCChangeRequestViewSet.as_view({"get": "list", "post": "create"}),
        name="databricks-uc-change-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/",
        UCChangeRequestViewSet.as_view({"get": "retrieve"}),
        name="databricks-uc-change-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/submit/",
        UCChangeRequestViewSet.as_view({"post": "submit"}),
        name="databricks-uc-change-submit",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/approve/",
        UCChangeRequestViewSet.as_view({"post": "approve"}),
        name="databricks-uc-change-approve",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/reject/",
        UCChangeRequestViewSet.as_view({"post": "reject"}),
        name="databricks-uc-change-reject",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/timeline/",
        UCChangeRequestViewSet.as_view({"get": "timeline"}),
        name="databricks-uc-change-timeline",
    ),
    path(
        "workspaces/<uuid:workspace_id>/uc/changes/<uuid:pk>/comments/",
        UCChangeRequestViewSet.as_view({"get": "comments", "post": "comments"}),
        name="databricks-uc-change-comments",
    ),
    path(
        "uc/changes/pending-approvals/",
        UCApprovalInboxViewSet.as_view({"get": "list"}),
        name="databricks-uc-change-inbox",
    ),
]

# Delta Sharing protocol endpoints (task 5.3) — the native 1.0 surface
# under /api/v1/databricks/delta-sharing/ (the oracle's path shapes).
from hub.apps.databricks_admin.delta_sharing_views import DeltaSharingProtocolViewSet

urlpatterns += [
    path(
        "delta-sharing/profile",
        DeltaSharingProtocolViewSet.as_view({"get": "profile"}),
        name="delta-sharing-profile",
    ),
    path(
        "delta-sharing/shares",
        DeltaSharingProtocolViewSet.as_view({"get": "list_shares"}),
        name="delta-sharing-shares",
    ),
    path(
        "delta-sharing/shares/<str:share>",
        DeltaSharingProtocolViewSet.as_view({"get": "get_share"}),
        name="delta-sharing-share",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas",
        DeltaSharingProtocolViewSet.as_view({"get": "list_schemas"}),
        name="delta-sharing-schemas",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas/<str:schema>/tables",
        DeltaSharingProtocolViewSet.as_view({"get": "list_tables"}),
        name="delta-sharing-tables",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas/<str:schema>/tables/<str:table>",
        DeltaSharingProtocolViewSet.as_view({"get": "get_table"}),
        name="delta-sharing-table",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas/<str:schema>/tables/<str:table>/metadata",
        DeltaSharingProtocolViewSet.as_view({"get": "get_metadata"}),
        name="delta-sharing-table-metadata",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas/<str:schema>/tables/<str:table>/version",
        DeltaSharingProtocolViewSet.as_view({"get": "get_version"}),
        name="delta-sharing-table-version",
    ),
    path(
        "delta-sharing/shares/<str:share>/schemas/<str:schema>/tables/<str:table>/query",
        DeltaSharingProtocolViewSet.as_view({"post": "query_table"}),
        name="delta-sharing-table-query",
    ),
]

# Cost-budget page (task 7.6 — the U9 budget page): the tenant's budget
# rows with the rolling progress + the per-warehouse breakdown.
from hub.apps.databricks_admin.budget_views import BudgetViewSet

urlpatterns += [
    path(
        "budgets/",
        BudgetViewSet.as_view({"get": "list"}),
        name="databricks-budget-list",
    ),
]
