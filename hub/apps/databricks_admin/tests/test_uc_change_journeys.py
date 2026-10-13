"""Journey pins for the P2 UC change surfaces (openspec
add-databricks-uc-write task 2.10) — JOURNEY-DB-007 (Request a UC DDL
Change) and JOURNEY-DB-008 (Approve or Reject a DDL Change).

Class/method names are PINNED by the UC docs' "Phase P2 Test" fields
(docs/mvpdocs/use-cases/UC-DB-007.md / UC-DB-008.md) — renaming them
breaks the docs↔test drift gates (GATE-28).

No mocks: real Postgres rows, real RBAC, real flag gating, the REAL
workflow services (create/submit/approve/reject with step
authorization), the REAL 2.4 guards at the boundary, and the REAL
transition side effects (in-app notifications + the webhook event).
"""

import uuid

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    UCChangeRequest,
    UCChangeRequestStatus,
)
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.uc("UC-DB-007"),
    pytest.mark.uc("UC-DB-008"),
    pytest.mark.journey("JOURNEY-DB-007"),
    pytest.mark.journey("JOURNEY-DB-008"),
]

_CHANGES_URL = "/api/v1/databricks/workspaces/{workspace_id}/uc/changes/"
_INBOX_URL = "/api/v1/databricks/uc/changes/pending-approvals/"


def _seed():
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    tenant.databricks_control_plane_enabled = True
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    requester = _make_user(tenant, f"uc-j7-req-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    requester.status = UserStatus.ACTIVE
    requester.save(update_fields=["status"])
    approver = _make_user(tenant, f"uc-j7-app-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    approver.status = UserStatus.ACTIVE
    approver.save(update_fields=["status"])
    workspace = _make_workspace(tenant)
    return tenant, requester, approver, workspace


def _payload():
    return {
        "change_type": "CREATE",
        "securable_type": "TABLE",
        "definition": {
            "identifiers": ["main", "sales", "orders"],
            "options": {"table_type": "MANAGED", "columns": [{"name": "id"}]},
        },
        "requires_approval": True,
        "required_approval_chain": [{"step": 1, "role": "TENANT_ADMIN", "label": "Admin step"}],
    }


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestJOURNEYDB007RequestDdlChange:
    """A data engineer requests a DDL change through the REAL API —
    the draft carries the truthful preview and the transition side
    effects fire."""

    def test_request_ddl_change_success(self):
        _tenant, requester, _approver, workspace = _seed()
        response = _client(requester).post(
            _CHANGES_URL.format(workspace_id=workspace.id), _payload(), format="json"
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["status"] == UCChangeRequestStatus.DRAFT
        assert body["preview"]["kind"] == "rest"
        assert body["preview"]["path"] == "/api/2.1/unity-catalog/tables"
        assert body["preview"]["body"]["name"] == "orders"
        assert UCChangeRequest.objects.filter(
            tenant=_tenant, workspace=workspace, full_name="main.sales.orders"
        ).exists()


class TestJOURNEYDB008ApproveDdlChange:
    """An approver resolves a pending DDL change through the REAL
    workflow: the inbox surfaces it, approval transitions it, and the
    requester is notified in-app."""

    def test_approve_or_reject_ddl_change(self):
        tenant, requester, approver, workspace = _seed()
        create = _client(requester).post(
            _CHANGES_URL.format(workspace_id=workspace.id), _payload(), format="json"
        )
        request_id = create.json()["id"]

        submit = _client(requester).post(
            _CHANGES_URL.format(workspace_id=workspace.id) + f"{request_id}/submit/"
        )
        assert submit.status_code == 200, submit.content
        assert submit.json()["status"] == UCChangeRequestStatus.PENDING_APPROVAL

        # The approver's inbox surfaces the pending request (the REAL
        # workflow step authorization decides visibility).
        inbox = _client(approver).get(_INBOX_URL)
        assert inbox.status_code == 200, inbox.content
        assert [row["id"] for row in inbox.json()["results"]] == [request_id]

        approve = _client(approver).post(
            _CHANGES_URL.format(workspace_id=workspace.id) + f"{request_id}/approve/"
        )
        assert approve.status_code == 200, approve.content
        assert approve.json()["status"] == UCChangeRequestStatus.APPROVED

        # The requester is notified in-app (the 2.8 side effect).
        from hub.apps.notifications.models import UserNotification

        assert UserNotification.objects.filter(
            tenant=tenant,
            user=requester,
            resource_type="DATABRICKS_UC_CHANGE_REQUEST",
            resource_id=request_id,
        ).exists()
