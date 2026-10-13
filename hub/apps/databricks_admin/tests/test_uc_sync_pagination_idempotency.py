"""Phase 1 (openspec add-databricks-uc-read task 1.12) — the UC REST
pagination loop and the sync's idempotency contract.

The spec's "Mirror refresh is idempotent" scenario is pinned at the SYNC
level (not the delta level): a second run over an unchanged fixture
estate writes NOTHING — no creates, no updates, no deletes, and the
``synced_at`` freshness stamps are untouched (the DB-005 marker). A
changed fixture row flips exactly ONE row.

The pagination loop is pinned with the multi-page fixture served by the
REAL local HTTP server through the PRODUCTION client: every page is
fetched exactly once with the continuation token, and a server that
repeats its ``next_page_token`` forever must FAIL the sync with a
classified error instead of looping (the loop-guard pin — without the
guard the sync hangs, proven by the RED run under a timeout).

No mocks: real Postgres mirrors, real Fernet M2M credential, real
Phase-272 approver linkage, real audit rows.
"""

import http.server
import json
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.databricks_admin.models import UCTable
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import UCEstateHandler
from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture
from hub.apps.databricks_admin.tests.test_uc_sync import (
    _local_client_factory,
    _make_approval,
    _make_credential,
    _make_workspace,
    _routes_for,
    _start_estate_server,
    _stop_estate_server,
)
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

UC = "/api/2.1/unity-catalog"


class _LoopingPagesHandler(UCEstateHandler):
    """A UC server that ALWAYS returns the same page with the same
    ``next_page_token`` — a real workspace bug surface. The repeating
    surface is ``catalogs`` (the FIRST workspace-scoped fetch), so
    without a loop guard the sync's pagination loop never terminates."""

    def _handle(self):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        type(self).requests.append(
            {
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "authorization": self.headers.get("Authorization"),
            }
        )
        if parsed.path == "/oidc/v1/token":
            body = type(self).token_body
        else:
            body = json.dumps(
                {
                    "catalogs": [
                        {
                            "name": "main",
                            "full_name": "main",
                            "catalog_type": "MANAGED",
                        }
                    ],
                    "next_page_token": "repeating-token",
                }
            ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


class _SyncSetupMixin:
    def _setup_sync(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"ucs-112-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.approval = _make_approval(self.tenant, self.admin)
        _make_credential(self.workspace, self.approval)
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)

        import hub.apps.databricks_admin.uc_sync as uc_sync_module

        self._original_factory = uc_sync_module._build_uc_client
        uc_sync_module._build_uc_client = _local_client_factory(self.port)
        self.addCleanup(setattr, uc_sync_module, "_build_uc_client", self._original_factory)

    def _sync(self, estate=None):
        """Run the sync. ``estate`` (optional) re-arms the scripted
        server's single-use envelopes for THIS run — a real workspace
        serves its estate on every fetch; the scripted routes are popped
        per request (run 2 over consumed routes would fetch ``{}`` and
        delete the whole mirror — a pin-infra trap, not sync behavior)."""
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        if estate is not None:
            UCEstateHandler.routes = _routes_for(estate)
        return sync_uc_workspace(self.workspace)


class UCSyncPaginationTests(TestCase, _SyncSetupMixin):
    """The UC REST pagination loop follows continuation tokens exactly."""

    def setUp(self):
        self._setup_sync()

    def test_multi_page_estate_is_fetched_exactly_once(self):
        UCEstateHandler.routes = load_fixture("estate_multi_page")["routes"]

        outcome = self._sync()
        assert "counters" in outcome, outcome

        tables_pages = [r for r in UCEstateHandler.requests if r["path"] == f"{UC}/tables"]
        assert len(tables_pages) == 2, "the fixture's 2 table pages must each be fetched once"
        assert "page_token" not in tables_pages[0]["query"], "page 1 carries no continuation"
        assert tables_pages[0]["query"]["max_results"] == ["100"]
        assert tables_pages[1]["query"]["page_token"] == ["tok-tables-1"], (
            "page 2 must carry the fixture's continuation token"
        )
        assert tables_pages[1]["query"]["max_results"] == ["100"]

        models_pages = [r for r in UCEstateHandler.requests if r["path"] == f"{UC}/models"]
        assert len(models_pages) == 2
        assert models_pages[1]["query"]["page_token"] == ["tok-models-1"]

        # Both pages landed: every fixture table is mirrored.
        names = set(
            UCTable.objects.filter(schema__catalog__workspace=self.workspace).values_list(
                "name", flat=True
            )
        )
        estate = load_fixture("estate")
        assert names == {t["name"] for t in estate["tables"]}

    def test_repeating_page_token_raises_a_classified_error(self):
        # RED (pre-guard): this pin HANGS — the loop follows the
        # repeating token forever. Proven under a shell timeout before the
        # guard landed. GREEN: the sync raises the classified error and
        # the failure audit/metric path runs (the 1.10 contract).
        import threading

        from hub.apps.databricks_admin.client import DatabricksApiError

        UCEstateHandler.routes = {}
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _LoopingPagesHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)

        import hub.apps.databricks_admin.uc_sync as uc_sync_module
        from hub.apps.audit.event_types import DATABRICKS_UC_METADATA_SYNC_FAILED
        from hub.apps.audit.models import AuditEvent

        uc_sync_module._build_uc_client = _local_client_factory(port)
        with pytest.raises(DatabricksApiError) as exc_info:
            self._sync()
        assert "next_page_token" in str(exc_info.value), (
            "the classified error must name the pagination-loop cause"
        )

        failed_audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_type="DATABRICKS_WORKSPACE",
                resource_id=str(self.workspace.id),
                action=DATABRICKS_UC_METADATA_SYNC_FAILED,
            )
            .order_by("-timestamp")
            .first()
        )
        assert failed_audit is not None, (
            "the loop-guard failure must emit the workspace-scoped SYNC_FAILED row"
        )
        assert "error_type" in failed_audit.details_json


class UCSyncIdempotencyTests(TestCase, _SyncSetupMixin):
    """The spec scenario: a second run over an unchanged estate writes
    nothing and leaves the freshness stamps alone."""

    def setUp(self):
        self._setup_sync()
        UCEstateHandler.routes = _routes_for(load_fixture("estate"))

    def _stamps(self):
        # Scoped to THIS workspace: the shared DB accumulates leaked rows
        # from parallel sessions (the 0.9 convention — global scans are
        # not robust there).
        from hub.apps.databricks_admin.models import (
            UCCatalog,
            UCExternalLocation,
            UCModel,
            UCSchema,
            UCStorageCredential,
            UCView,
            UCVolume,
        )

        stamp = {}
        workspace_models = (UCCatalog, UCExternalLocation, UCStorageCredential)
        for model in workspace_models:
            for row in model.objects.filter(workspace=self.workspace):
                stamp[(model.__name__, str(row.id))] = row.synced_at
        for row in UCSchema.objects.filter(catalog__workspace=self.workspace):
            stamp[("UCSchema", str(row.id))] = row.synced_at
        for model in (UCTable, UCView, UCVolume, UCModel):
            for row in model.objects.filter(schema__catalog__workspace=self.workspace):
                stamp[(model.__name__, str(row.id))] = row.synced_at
        return stamp

    def test_second_run_over_an_unchanged_estate_writes_nothing(self):
        from hub.apps.audit.event_types import DATABRICKS_UC_METADATA_SYNCED
        from hub.apps.audit.models import AuditEvent

        estate = load_fixture("estate")
        first = self._sync(estate=estate)
        assert first["counters"]["created"] == 9, first
        stamps_before = self._stamps()

        second = self._sync(estate=estate)
        assert second["counters"] == {
            "created": 0,
            "updated": 0,
            "unchanged": 9,
            "deleted": 0,
        }, "an unchanged fixture estate must be a full no-op on the second run"

        assert self._stamps() == stamps_before, (
            "the second run must not rewrite a single synced_at freshness stamp"
        )
        synced_rows = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_type="DATABRICKS_WORKSPACE",
                resource_id=str(self.workspace.id),
                action=DATABRICKS_UC_METADATA_SYNCED,
            )
            .order_by("timestamp")
            .count()
        )
        assert synced_rows == 2, "each run must emit its own SYNCED audit row"

    def test_changed_fixture_row_updates_exactly_one_mirror_row(self):
        self._sync(estate=load_fixture("estate"))
        stamps_before = self._stamps()

        estate = load_fixture("estate")
        estate["tables"][0]["comment"] = "Order fact table — v2"

        outcome = self._sync(estate=estate)
        assert outcome["counters"] == {
            "created": 0,
            "updated": 1,
            "unchanged": 8,
            "deleted": 0,
        }, "exactly the changed table must be rewritten"

        stamps_after = self._stamps()
        changed = [key for key in stamps_before if stamps_before[key] != stamps_after[key]]
        assert len(changed) == 1, "only the changed row's synced_at must advance"
        assert changed[0][0] == "UCTable", "the advanced stamp must be the table"
        updated = UCTable.objects.get(schema__catalog__workspace=self.workspace, name="orders")
        assert updated.comment == "Order fact table — v2"
        assert (
            stamps_after[("UCTable", str(updated.id))] > stamps_before[("UCTable", str(updated.id))]
        )

    def test_removed_fixture_row_deletes_only_that_mirror_row(self):
        self._sync(estate=load_fixture("estate"))

        estate = load_fixture("estate")
        estate["tables"] = estate["tables"][:1]  # drop "customers"

        outcome = self._sync(estate=estate)
        assert outcome["counters"]["deleted"] == 1, outcome
        assert not UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="customers"
        ).exists()
        assert UCTable.objects.filter(
            schema__catalog__workspace=self.workspace, name="orders"
        ).exists()

    def test_synced_at_is_a_real_timestamp(self):
        self._sync(estate=load_fixture("estate"))
        stamps = self._stamps()
        now = timezone.now()
        for value in stamps.values():
            assert value is not None
            assert abs((now - value).total_seconds()) < 300, "stamps must be recent"
