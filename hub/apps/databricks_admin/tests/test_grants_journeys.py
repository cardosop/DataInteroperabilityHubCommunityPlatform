"""Journey pins for the P2 grants surface (openspec
add-databricks-uc-write task 2.10) — JOURNEY-DB-009 (Manage UC Grants).

Class/method names are PINNED by the UC docs' "Phase P2 Test" field
(docs/mvpdocs/use-cases/UC-DB-009.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

No mocks: real Postgres ABAC policies + real bindings/principals, the
REAL plan→diff→apply bridge, and the PRODUCTION client against a REAL
local HTTP server for the PATCH leg (the exact permissions endpoint
path + the remove-then-add changes body are asserted).
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.uc("UC-DB-009"),
    pytest.mark.journey("JOURNEY-DB-009"),
]


class TestJOURNEYDB009ManageUcGrants(TestCase):
    """An MPA manages UC grants: the ABAC policy plans the intent, the
    bridge diffs it against the live assignments and applies the delta
    through the REAL PATCH leg."""

    def test_manage_uc_grants(self):
        import http.server
        import threading

        require_dns()
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        _make_user(tenant, f"uc-j9-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        workspace = _make_workspace(tenant)

        from hub.apps.governance.models import AccessPolicy

        policy = AccessPolicy.objects.create(
            tenant=tenant,
            name="grant-table-select",
            conditions={
                "uc_grant": {
                    "securable_type": "TABLE",
                    "securable_full_name": "main.sales.orders",
                    "principal": "data-team",
                    "privileges": ["SELECT"],
                }
            },
            effect="ALLOW",
            enabled=True,
        )

        # The plan derives the intended grant from the REAL policy row.
        from hub.apps.databricks_admin.uc_grants_bridge import plan_uc_grants

        intended = plan_uc_grants(workspace)
        assert intended == [
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT"],
            }
        ]
        assert policy.enabled

        # The apply leg drives the PRODUCTION client against a real
        # local HTTP server (the exact PATCH + permissions path).
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = [json.dumps({"privilege_assignments": []})]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)

        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(tenant.id),
            credential_config={"token": "dapi-journey"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
        apply_grant_delta(
            client,
            workspace=workspace,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            changes={"add": [("data-team", "SELECT")], "remove": []},
        )
        request = RecordingHandler.requests[-1]
        assert request["method"] == "PATCH"
        assert request["path"] == "/api/2.1/unity-catalog/permissions/table/main.sales.orders"
        body = json.loads(request["body"])
        assert body["changes"] == [{"principal": "data-team", "add": ["SELECT"]}]
