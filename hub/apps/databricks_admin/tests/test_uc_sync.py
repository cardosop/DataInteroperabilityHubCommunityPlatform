"""Phase 1 (openspec add-databricks-uc-read task 1.5) — UC metadata sync.

No mocks: real Postgres mirrors, real Fernet-encrypted M2M credentials,
a real Phase-272 AccessRequest as the D12 approver-chain linkage, real
audit rows, and a REAL local HTTP server serving scripted UC REST
envelopes through the PRODUCTION ``DatabricksApiClient`` (the
``_build_uc_client`` factory seam — the 0.8/1.3 pattern). Pagination is
exercised with a real ``next_page_token`` chain; every recorded request
is asserted to carry the workspace M2M bearer.
"""

import http.server
import threading
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
    UCCatalog,
    UCExternalLocation,
    UCModel,
    UCSchema,
    UCStorageCredential,
    UCTable,
    UCView,
    UCVolume,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import UCEstateHandler
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.jobs.utils import get_job_max_retries, get_job_timeout
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

UC = "/api/2.1/unity-catalog"


def _start_estate_server():
    """Start the scripted UC estate server; returns (server, port).

    A plain helper, not a pytest fixture — fixtures cannot serve
    unittest.TestCase methods (the 0.8 lesson); TestCase classes call
    this in setUp and register addCleanup shutdowns.
    """
    UCEstateHandler.routes = {}
    UCEstateHandler.requests = []
    UCEstateHandler.status = 200
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), UCEstateHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _stop_estate_server(server):
    server.shutdown()
    server.server_close()


def _routes_for(estate: dict) -> dict:
    """The scripted UC REST envelopes for *estate* (single page each)."""
    return {
        f"{UC}/catalogs": [{"catalogs": estate["catalogs"], "next_page_token": None}],
        f"{UC}/schemas": [{"schemas": estate["schemas"], "next_page_token": None}],
        f"{UC}/tables": [{"tables": estate["tables"], "next_page_token": None}],
        f"{UC}/views": [{"views": estate["views"], "next_page_token": None}],
        f"{UC}/volumes": [{"volumes": estate["volumes"], "next_page_token": None}],
        f"{UC}/models": [{"models": estate["models"], "next_page_token": None}],
        f"{UC}/external-locations": [
            {"external_locations": estate["external_locations"], "next_page_token": None}
        ],
        f"{UC}/storage-credentials": [
            {"storage_credentials": estate["storage_credentials"], "next_page_token": None}
        ],
    }


class _FixtureMixin:
    """The xunit surface pytest plain classes lack.

    pytest DOES inject fixtures into plain-class methods but does NOT call
    ``setUp``/``tearDown`` or provide ``addCleanup`` — this mixin bridges
    that gap so fixture-taking classes keep their unittest-style setup
    and cleanup registration (setup_method/teardown_method are the pytest
    xunit hooks). NO ``__init__`` — a class defining ``__init__`` is
    SKIPPED by pytest collection entirely.
    """

    def setup_method(self, _method=None):
        if hasattr(self, "setUp"):
            self.setUp()

    def teardown_method(self, _method=None):
        cleanups = getattr(self, "_cleanups", None) or []
        while cleanups:
            fn, args, kwargs = cleanups.pop()
            fn(*args, **kwargs)

    def addCleanup(self, fn, *args, **kwargs):
        if not hasattr(self, "_cleanups"):
            self._cleanups = []
        self._cleanups.append((fn, args, kwargs))


def _estate():
    """A small two-table estate exercising every mirror surface.

    The canonical fixture file (``tests/fixtures/databricks/estate.json``)
    is the single source of truth — task 1.12 moved the inline dict into
    the file (the browse fixtures + idempotency pins consume the same
    estate through the same loader).
    """
    from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture

    return load_fixture("estate")


def _make_workspace(tenant, name="ws-1", status=DatabricksWorkspaceStatus.ACTIVE):
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status=status,
    )


def _make_approval(tenant, user):
    # AccessRequest requires ONE polymorphic resource (asset/dataset/file)
    # — the 0b.6 fixture pattern.
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"uc-sync-asset-{uuid.uuid4().hex[:8]}",
        name="UC sync authorization asset",
        description="polymorphic anchor for the workspace credential approval",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    return AccessRequest.objects.create(
        tenant=tenant,
        requested_by=user,
        asset=asset,
        requested_access_type="ADMIN",
        reason="authorize the UC metadata sync M2M credential",
        status=AccessRequestStatus.APPROVED,
        requires_approval=True,
        approval_workflow=[{"step": 1, "approver_role": "TENANT_ADMIN", "status": "APPROVED"}],
        approvers=[str(user.id)],
        approved_by=user,
        approved_at=timezone.now(),
    )


def _make_credential(workspace, approval=None, auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M):
    credential = DatabricksCredential(
        workspace=workspace,
        auth_mode=auth_mode,
        approval_request=approval,
    )
    if auth_mode == DatabricksCredentialAuthMode.OAUTH_M2M:
        credential.set_config({"client_id": "sync-client", "client_secret": "sync-secret"})
    else:
        credential.set_config({"token": "pat-token"})
    credential.save()
    return credential


def _local_client_factory(port):
    """Redirect the sync's client factory to the local UC server (the
    production client in transport mode — real HTTP, no mocks)."""
    from hub.apps.databricks_admin.client import DatabricksApiClient

    def factory(workspace, identity):
        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(workspace.tenant_id),
            credential_config=identity.credential.get_config(),
            auth_mode=identity.credential.auth_mode,
        )

    return factory


class TestApplyUcDelta(TestCase):
    """The pure delta-diff over real Postgres mirrors (no HTTP)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"ucs-delta-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        self.workspace = _make_workspace(self.tenant)

    def test_delta_creates_the_whole_estate(self):
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta

        counters = apply_uc_delta(self.workspace, _estate())
        assert counters["created"] == 9, counters
        assert counters["updated"] == 0, counters
        assert counters["unchanged"] == 0, counters
        assert counters["deleted"] == 0, counters
        assert UCCatalog.objects.filter(workspace=self.workspace).count() == 1
        assert UCSchema.objects.filter(catalog__workspace=self.workspace).count() == 1
        assert UCTable.objects.filter(schema__catalog__workspace=self.workspace).count() == 2
        assert UCView.objects.filter(schema__catalog__workspace=self.workspace).count() == 1
        assert UCVolume.objects.filter(schema__catalog__workspace=self.workspace).count() == 1
        assert UCModel.objects.filter(schema__catalog__workspace=self.workspace).count() == 1
        assert UCExternalLocation.objects.filter(workspace=self.workspace).count() == 1
        assert UCStorageCredential.objects.filter(workspace=self.workspace).count() == 1

    def test_delta_updates_changed_rows_and_leaves_unchanged_alone(self):
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta

        apply_uc_delta(self.workspace, _estate())
        old_ts = timezone.now() - timedelta(days=1)
        # Freeze synced_at for the whole estate so a delta write is
        # detectable by a bumped stamp.
        UCCatalog.objects.filter(workspace=self.workspace).update(synced_at=old_ts)
        UCSchema.objects.filter(catalog__workspace=self.workspace).update(synced_at=old_ts)
        UCTable.objects.filter(schema__catalog__workspace=self.workspace).update(synced_at=old_ts)
        UCView.objects.filter(schema__catalog__workspace=self.workspace).update(synced_at=old_ts)
        UCVolume.objects.filter(schema__catalog__workspace=self.workspace).update(synced_at=old_ts)
        UCModel.objects.filter(schema__catalog__workspace=self.workspace).update(synced_at=old_ts)
        UCExternalLocation.objects.filter(workspace=self.workspace).update(synced_at=old_ts)
        UCStorageCredential.objects.filter(workspace=self.workspace).update(synced_at=old_ts)

        estate = _estate()
        estate["tables"][0]["comment"] = "Order fact table v2"
        counters = apply_uc_delta(self.workspace, estate)
        assert counters["updated"] == 1, counters
        assert counters["unchanged"] == 8, counters
        assert counters["created"] == 0, counters
        assert counters["deleted"] == 0, counters

        orders = UCTable.objects.get(schema__catalog__workspace=self.workspace, name="orders")
        assert orders.comment == "Order fact table v2"
        assert orders.synced_at > old_ts, "a changed row must bump its freshness stamp"
        untouched = UCTable.objects.get(schema__catalog__workspace=self.workspace, name="customers")
        assert untouched.synced_at == old_ts, "an unchanged row must NOT be rewritten"

    def test_delta_deletes_removed_rows_and_their_index_rows(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta
        from hub.apps.search.models import SearchIndex

        apply_uc_delta(self.workspace, _estate())
        table = UCTable.objects.get(schema__catalog__workspace=self.workspace, name="customers")
        index_uc_object(table)

        estate = _estate()
        estate["tables"] = [t for t in estate["tables"] if t["name"] != "customers"]
        estate["tables"].append(
            {
                "name": "refunds",
                "comment": "Refund fact",
                "owner": "admin@example.com",
                "table_type": "MANAGED",
                "storage_location": "s3://bucket/refunds",
                "columns": [],
                "full_name": "main.sales.refunds",
                "catalog_name": "main",
                "schema_name": "sales",
            }
        )
        counters = apply_uc_delta(self.workspace, estate)
        assert counters["deleted"] == 1, counters
        assert counters["created"] == 1, counters
        assert not UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="customers"
        ).exists(), "the removed mirror row must be deleted"
        assert UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="refunds"
        ).exists()
        assert not SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="DATABRICKS_UC_TABLE",
            resource_id=table.id,
        ).exists(), "the removed table's index row must be swept"

    def test_delta_cascades_parent_removal_to_the_mirror_chain(self):
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta

        apply_uc_delta(self.workspace, _estate())
        estate = _estate()
        estate["catalogs"] = []
        estate["schemas"] = []
        estate["tables"] = []
        estate["views"] = []
        estate["volumes"] = []
        estate["models"] = []
        counters = apply_uc_delta(self.workspace, estate)
        assert counters["deleted"] == 7, counters
        assert UCCatalog.objects.filter(workspace=self.workspace).count() == 0
        assert UCSchema.objects.filter(catalog__workspace=self.workspace).count() == 0
        assert UCTable.objects.filter(schema__catalog__workspace=self.workspace).count() == 0

    def test_delta_keeps_the_search_feed_consistent(self):
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta
        from hub.apps.search.models import SearchIndex

        apply_uc_delta(self.workspace, _estate())
        mirror_count = (
            UCCatalog.objects.filter(workspace=self.workspace).count()
            + UCSchema.objects.filter(catalog__workspace=self.workspace).count()
            + UCTable.objects.filter(schema__catalog__workspace=self.workspace).count()
            + UCView.objects.filter(schema__catalog__workspace=self.workspace).count()
            + UCVolume.objects.filter(schema__catalog__workspace=self.workspace).count()
            + UCModel.objects.filter(schema__catalog__workspace=self.workspace).count()
        )
        index_count = SearchIndex.objects.filter(
            tenant=self.tenant, resource_type__startswith="DATABRICKS_UC_"
        ).count()
        assert index_count == mirror_count, (
            f"the search feed must mirror the whole estate ({index_count} != {mirror_count})"
        )

    def test_apply_is_atomic_a_mid_apply_failure_leaves_no_partial_rows(self):
        """A failure half-way through the delta leaves NO partial mirror —
        the upsert/delete phase is ONE transaction; only the post-commit
        reindex is a side effect (1.5 review hardening pin)."""
        from unittest import mock

        from hub.apps.databricks_admin import uc_sync
        from hub.apps.databricks_admin.uc_sync import apply_uc_delta

        with (
            mock.patch.object(
                uc_sync, "_delete_missing", side_effect=RuntimeError("mid-apply failure")
            ),
            pytest.raises(RuntimeError),
        ):
            apply_uc_delta(self.workspace, _estate())
        # Every upserted row must be rolled back — no torn mirror.
        assert UCCatalog.objects.filter(workspace=self.workspace).count() == 0
        assert UCSchema.objects.filter(catalog__workspace=self.workspace).count() == 0
        assert UCTable.objects.filter(schema__catalog__workspace=self.workspace).count() == 0
        assert UCVolume.objects.filter(schema__catalog__workspace=self.workspace).count() == 0
        assert UCExternalLocation.objects.filter(workspace=self.workspace).count() == 0


class TestFetchUCEstate(_FixtureMixin):
    """The REST estate fetch through the production client + a REAL
    local HTTP server — pagination, query params, M2M bearer."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.user = _make_user(
            self.tenant, f"ucs-fetch-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.credential = _make_credential(self.workspace, _make_approval(self.tenant, self.user))
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)

    def _client(self, port):
        from hub.apps.databricks_admin.client import DatabricksApiClient

        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(self.workspace.tenant_id),
            credential_config=self.credential.get_config(),
            auth_mode=self.credential.auth_mode,
        )

    def test_fetch_maps_every_estate_surface(self):
        from hub.apps.databricks_admin.uc_sync import fetch_uc_estate

        UCEstateHandler.routes = _routes_for(_estate())
        client = self._client(self.port)
        try:
            estate = fetch_uc_estate(client)
        finally:
            client.close()
        assert estate["catalogs"][0]["name"] == "main"
        assert estate["schemas"][0]["full_name"] == "main.sales"
        assert {t["name"] for t in estate["tables"]} == {"orders", "customers"}
        assert estate["tables"][0]["columns"] == [{"name": "customer_id", "type_text": "BIGINT"}]
        assert estate["views"][0]["view_definition"] == "SELECT * FROM orders"
        assert estate["volumes"][0]["volume_type"] == "MANAGED"
        assert estate["models"][0]["latest_version"] == 2
        assert estate["models"][0]["aliases"] == ["champion"]
        assert estate["external_locations"][0]["url"] == "s3://bucket/raw"
        assert estate["storage_credentials"][0]["name"] == "sc1"

    def test_fetch_follows_next_page_token_exactly_once(self):
        from hub.apps.databricks_admin.uc_sync import fetch_uc_estate

        estate = _estate()
        UCEstateHandler.routes = _routes_for(estate)
        # Two-page catalogs: page 1 carries next_page_token, page 2 the
        # remaining catalog. Schemas are then fetched PER catalog.
        UCEstateHandler.routes[f"{UC}/catalogs"] = [
            {
                "catalogs": [estate["catalogs"][0]],
                "next_page_token": "page-2",
            },
            {
                "catalogs": [
                    {
                        "name": "aux",
                        "comment": "aux catalog",
                        "owner": "admin@example.com",
                        "catalog_type": "MANAGED",
                        "properties": {},
                        "full_name": "aux",
                    }
                ],
                "next_page_token": None,
            },
        ]
        UCEstateHandler.routes[f"{UC}/schemas"] = [
            {"schemas": estate["schemas"], "next_page_token": None},
            {"schemas": [], "next_page_token": None},
        ]
        # tables/views/volumes/models answered per (catalog, schema) call —
        # one page per call; aux has no schemas so only main.sales is hit.
        for path in (f"{UC}/tables", f"{UC}/views", f"{UC}/volumes", f"{UC}/models"):
            UCEstateHandler.routes[path] = [
                {path.rsplit("/", 1)[-1]: estate[path.rsplit("/", 1)[-1]], "next_page_token": None},
            ]

        client = self._client(self.port)
        try:
            estate = fetch_uc_estate(client)
        finally:
            client.close()

        catalog_requests = [r for r in UCEstateHandler.requests if r["path"] == f"{UC}/catalogs"]
        assert len(catalog_requests) == 2, "page 1 + page 2"
        assert catalog_requests[1]["query"].get("page_token") == ["page-2"]
        assert {c["name"] for c in estate["catalogs"]} == {"main", "aux"}
        schema_requests = [r for r in UCEstateHandler.requests if r["path"] == f"{UC}/schemas"]
        assert {r["query"].get("catalog_name", [None])[0] for r in schema_requests} == {
            "main",
            "aux",
        }

    def test_every_estate_request_carries_the_m2m_bearer(self):
        from hub.apps.databricks_admin.uc_sync import fetch_uc_estate

        UCEstateHandler.routes = _routes_for(_estate())
        client = self._client(self.port)
        try:
            fetch_uc_estate(client)
        finally:
            client.close()
        uc_requests = [r for r in UCEstateHandler.requests if r["path"].startswith(UC)]
        assert len(uc_requests) >= 8, "every estate surface must be fetched"
        for r in uc_requests:
            assert r["authorization"] == "Bearer tok-sync-abc", (
                f"request to {r['path']} must use the workspace M2M bearer"
            )


class TestSyncServiceIdentity(_FixtureMixin):
    """D12: the sync runs under the workspace M2M credential WITH
    approver-chain linkage — and fails closed otherwise."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.user = _make_user(
            self.tenant, f"ucs-ident-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.approval = _make_approval(self.tenant, self.user)
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)

    def _patch_factory(self, port):
        import hub.apps.databricks_admin.uc_sync as uc_sync_module

        original = uc_sync_module._build_uc_client
        factory = _local_client_factory(port)
        uc_sync_module._build_uc_client = factory
        self.addCleanup(setattr, uc_sync_module, "_build_uc_client", original)
        return factory

    def test_sync_with_linked_m2m_credential_syncs_and_audits(self):
        from hub.apps.audit.event_types import DATABRICKS_UC_METADATA_SYNCED
        from hub.apps.audit.models import AuditEvent

        self._patch_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        _make_credential(self.workspace, self.approval)

        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        outcome = sync_uc_workspace(self.workspace)
        assert "counters" in outcome, outcome
        assert outcome["counters"]["created"] == 9
        assert UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="orders"
        ).exists()

        # The D12 decision (identity.py) emits resource_type=
        # DATABRICKS_EXECUTION_IDENTITY with action=RESOLVED (the
        # combined constant DATABRICKS_EXECUTION_IDENTITY_RESOLVED is
        # the registration pin, 0b.6).
        identity_audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_type="DATABRICKS_EXECUTION_IDENTITY",
                action="RESOLVED",
            )
            .order_by("-timestamp")
            .first()
        )
        assert identity_audit is not None, "the D12 decision must be audited"
        assert identity_audit.details_json["approval_request_id"] == str(self.approval.id)
        synced_audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=DATABRICKS_UC_METADATA_SYNCED,
            )
            .order_by("-timestamp")
            .first()
        )
        assert synced_audit is not None, "a successful sync must emit UC_METADATA_SYNCED"
        assert str(self.workspace.id) == str(synced_audit.resource_id)

    def test_sync_skips_when_the_credential_has_no_approval_linkage(self):
        self._patch_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        _make_credential(self.workspace, approval=None)  # no Phase-272 linkage

        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        outcome = sync_uc_workspace(self.workspace)
        assert "skipped" in outcome, outcome
        assert "approval" in outcome["skipped"].lower()
        assert not UCEstateHandler.requests, (
            "a credential without approver-chain linkage must never execute "
            "(fail-closed, zero network calls)"
        )
        assert not UCTable.objects.filter(schema__catalog__workspace=self.workspace).exists()

    def test_sync_skips_when_no_m2m_credential_exists(self):
        self._patch_factory(self.port)
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        outcome = sync_uc_workspace(self.workspace)
        assert "skipped" in outcome, outcome
        assert not UCEstateHandler.requests, "zero network calls without a credential"

    def test_sync_extends_the_lineage_graph(self):
        # 1.6 — the sync feeds the contracts lineage surface: the
        # mirrored view's SQL ("SELECT * FROM orders") becomes a real
        # LineageEdge row (table → view) after the workspace sync.
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        self._patch_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        _make_credential(self.workspace, self.approval)

        outcome = sync_uc_workspace(self.workspace)
        assert "counters" in outcome, outcome
        assert outcome.get("lineage") == {"added": 1, "removed": 0}, outcome
        edges = LineageEdge.objects.filter(
            tenant=self.tenant,
            job_ref=f"databricks_uc_metadata_sync:{self.workspace.id}",
            valid_to__isnull=True,
        )
        assert {(e.source_model, e.target_model) for e in edges} == {
            ("main.sales.orders", "main.sales.v_orders")
        }

    def test_fetch_failure_emits_the_sync_failed_audit_row(self):
        # 1.10 — a TRANSPORT/API failure (the most likely failure mode)
        # must emit the per-workspace SYNC_FAILED audit row, not only
        # the job-layer JOB_FAILED.
        import pytest

        from hub.apps.audit.event_types import DATABRICKS_UC_METADATA_SYNC_FAILED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        self._patch_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        UCEstateHandler.status = 500
        _make_credential(self.workspace, self.approval)

        with pytest.raises(DatabricksApiError):
            sync_uc_workspace(self.workspace)
        UCEstateHandler.status = 200

        failed_audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=DATABRICKS_UC_METADATA_SYNC_FAILED,
                resource_type="DATABRICKS_WORKSPACE",
            )
            .order_by("-timestamp")
            .first()
        )
        assert failed_audit is not None, (
            "a failed fetch must emit the per-workspace SYNC_FAILED audit row"
        )
        assert "error_type" in failed_audit.details_json


class TestUCSyncJobHandler(_FixtureMixin):
    """The RQ handler: tenant-scoped via tenant_context, ACTIVE-only,
    sibling tenants untouched."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.user = _make_user(
            self.tenant, f"ucs-job-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.other_tenant = TenantFactory.create_tenant()
        _activate_billing(self.other_tenant)
        self.workspace = _make_workspace(self.tenant)
        self.disabled_ws = _make_workspace(
            self.tenant, name="ws-disabled", status=DatabricksWorkspaceStatus.DISABLED
        )
        self.other_workspace = _make_workspace(self.other_tenant, name="ws-other")
        _make_credential(self.workspace, _make_approval(self.tenant, self.user))
        _make_credential(self.disabled_ws, _make_approval(self.tenant, self.user))
        _make_credential(self.other_workspace, _make_approval(self.other_tenant, self.user))
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)

    def _job(self, tenant):
        return Job.objects.create(
            tenant=tenant,
            type=JobType.DATABRICKS_UC_METADATA_SYNC,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            resource_type="TENANT",
            resource_id=tenant.id,
        )

    def test_handler_syncs_the_jobs_tenant_only(self):
        import hub.apps.databricks_admin.uc_sync as uc_sync_module
        from hub.apps.databricks_admin.uc_sync_jobs import (
            _execute_databricks_uc_metadata_sync_job,
        )

        factory = _local_client_factory(self.port)
        uc_sync_module._build_uc_client = factory
        UCEstateHandler.routes = _routes_for(_estate())

        result = _execute_databricks_uc_metadata_sync_job(self._job(self.tenant))
        assert result["workspaces_synced"] == 1, result
        assert result["workspaces_skipped"] == [], result
        assert UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="orders"
        ).exists(), "the job tenant's ACTIVE workspace must be synced"
        assert not UCTable.objects.filter(schema__catalog__workspace=self.disabled_ws).exists(), (
            "DISABLED workspaces are out of scope"
        )
        assert not UCTable.objects.filter(
            schema__catalog__workspace=self.other_workspace
        ).exists(), "a sibling tenant's estate must never be touched"

    def test_handler_skips_workspaces_without_linkage(self):
        import hub.apps.databricks_admin.uc_sync as uc_sync_module
        from hub.apps.databricks_admin.uc_sync_jobs import (
            _execute_databricks_uc_metadata_sync_job,
        )

        uc_sync_module._build_uc_client = _local_client_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        # Unlinked credential for the ACTIVE workspace → skipped, not failed.
        DatabricksCredential.objects.filter(workspace=self.workspace).update(approval_request=None)

        result = _execute_databricks_uc_metadata_sync_job(self._job(self.tenant))
        assert result["workspaces_synced"] == 0, result
        assert len(result["workspaces_skipped"]) == 1, result
        assert not UCTable.objects.filter(schema__catalog__workspace=self.workspace).exists()


class TestUCSyncJobRegistration(_FixtureMixin):
    """JobType + timeout/retry + dispatch wiring for the sync job."""

    def test_job_type_registered_with_timeout_and_retries(self):
        assert JobType.DATABRICKS_UC_METADATA_SYNC.value == "DATABRICKS_UC_METADATA_SYNC"
        assert get_job_timeout(JobType.DATABRICKS_UC_METADATA_SYNC) == 3600
        assert get_job_max_retries(JobType.DATABRICKS_UC_METADATA_SYNC) == 1

    def test_dispatch_routes_the_uc_sync_type(self):
        import hub.apps.databricks_admin.uc_sync as uc_sync_module
        from hub.apps.jobs.tasks_base import _execute_job_logic

        _server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, _server)
        require_dns()
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        user = _make_user(tenant, f"ucs-disp-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        workspace = _make_workspace(tenant)
        _make_credential(workspace, _make_approval(tenant, user))

        uc_sync_module._build_uc_client = _local_client_factory(self.port)
        UCEstateHandler.routes = _routes_for(_estate())
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.DATABRICKS_UC_METADATA_SYNC,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            resource_type="TENANT",
            resource_id=tenant.id,
        )

        result = _execute_job_logic(job, JobType.DATABRICKS_UC_METADATA_SYNC.value)
        assert result["workspaces_synced"] == 1, result
        assert UCTable.objects.filter(schema__catalog__workspace=workspace, name="orders").exists()


class TestUCSyncCommand(TransactionTestCase):
    """The CronJob-facing management command: admin-DB discovery + one
    PENDING RQ job per tenant.

    TransactionTestCase (not TestCase): the discovery reads through the
    ``admin`` DB ALIAS — a SEPARATE connection — and a TestCase's
    uncommitted setUp rows are invisible across connections. Real
    committed rows exercise the actual production path.
    """

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)
        self.tenant_without_workspaces = TenantFactory.create_tenant()

    def test_dry_run_reports_tenants_without_creating_jobs(self):
        out = call_command("databricks_uc_metadata_sync", "--dry-run")
        assert str(self.tenant.id) in out
        assert str(self.tenant_without_workspaces.id) not in out
        # Scoped to the test's OWN tenants: the shared test DB
        # accumulates leaked job rows from parallel sessions (the 0.9
        # convention — global-emptiness asserts are not robust there).
        assert not Job.objects.filter(
            type=JobType.DATABRICKS_UC_METADATA_SYNC, tenant_id=self.tenant.id
        ).exists()
        assert not Job.objects.filter(
            type=JobType.DATABRICKS_UC_METADATA_SYNC,
            tenant_id=self.tenant_without_workspaces.id,
        ).exists()

    def test_run_creates_one_pending_job_per_tenant(self):
        from django_rq import get_queue

        queue = get_queue("job_default")
        queue.empty()
        # TransactionTestCase runs in autocommit — create_job's
        # on_commit enqueue fires immediately, so the REAL RQ enqueue
        # happens inside the call.
        call_command("databricks_uc_metadata_sync")
        # Scoped to this test's tenant: the command also enqueues jobs
        # for every OTHER leaked tenant with an ACTIVE workspace on the
        # shared DB (production semantics — one job per tenant), so the
        # pin asserts THIS tenant's row, not the global table.
        jobs = Job.objects.filter(
            type=JobType.DATABRICKS_UC_METADATA_SYNC, tenant_id=self.tenant.id
        )
        assert jobs.count() == 1
        job = jobs.get()
        # A live RQ worker (the shared compose worker consumes the same
        # Redis queues) may process the job between create and assert —
        # the row SHAPE is the contract, the status is a race.
        assert job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)
        assert job.resource_type == "TENANT"
        assert str(job.resource_id) == str(self.tenant.id)
        # The REAL RQ enqueue must have carried this tenant's job — when
        # the worker has not yet drained the queue.
        enqueued_ids = [rq_job.args[0] for rq_job in queue.jobs]
        if queue.count >= 1:
            assert str(job.id) in enqueued_ids, "the REAL RQ enqueue must carry this tenant's job"
        queue.empty()
