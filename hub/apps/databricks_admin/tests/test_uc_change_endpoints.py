"""TDD pins for the U4 API surface (openspec add-databricks-uc-write
task 2.8) — the change-request endpoints.

Real Postgres + real RBAC + real workflow functions; the endpoints are
nested under the workspace registry (`/api/v1/databricks/workspaces/
{id}/uc/changes/`) plus the cross-workspace approver inbox
(`/api/v1/databricks/uc/changes/pending-approvals/`). Gates: the
control-plane flag, authentication, tenant scoping, and the Phase 273
throttle scope.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed(flag=True):
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    tenant.databricks_control_plane_enabled = flag
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    requester = _make_user(tenant, f"uc-ep-req-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    requester.status = UserStatus.ACTIVE
    requester.save(update_fields=["status"])
    approver = _make_user(tenant, f"uc-ep-app-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    approver.status = UserStatus.ACTIVE
    approver.save(update_fields=["status"])
    workspace = _make_workspace(tenant)
    return tenant, requester, approver, workspace


def _client(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _url(workspace_id, tail=""):
    return f"/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{tail}"


def _create_payload():
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


class UCChangeEndpointTests(TestCase):
    def setUp(self):
        self.tenant, self.requester, self.approver, self.workspace = _seed()

    def test_create_returns_a_draft_with_the_preview(self):
        response = _client(self.requester).post(
            _url(self.workspace.id), _create_payload(), format="json"
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["status"] == "DRAFT"
        assert body["preview"]["kind"] == "rest"
        assert body["preview"]["path"] == "/api/2.1/unity-catalog/tables"

    def test_create_rejects_malformed_identifiers_at_the_boundary(self):
        payload = _create_payload()
        payload["definition"]["identifiers"] = ["main", "sales", "bad;DROP--"]
        response = _client(self.requester).post(_url(self.workspace.id), payload, format="json")
        assert response.status_code == 400, response.content
        assert response.json()["code"] == "DATABRICKS_DDL_INVALID_IDENTIFIER"

    def test_create_rejects_a_destructive_request_on_a_flag_off_tenant(self):
        payload = _create_payload()
        payload["change_type"] = "DROP"
        response = _client(self.requester).post(_url(self.workspace.id), payload, format="json")
        assert response.status_code == 403, response.content
        assert response.json()["code"] == "DATABRICKS_DDL_DENYLISTED"

    def test_list_is_paginated_and_workspace_scoped(self):
        from hub.apps.databricks_admin.models import UCChangeRequest

        UCChangeRequest.objects.create(
            tenant=self.tenant,
            workspace=self.workspace,
            requested_by=self.requester,
            change_type="CREATE",
            securable_type="TABLE",
            full_name="main.sales.orders",
            definition={"identifiers": ["main", "sales", "orders"]},
        )
        response = _client(self.requester).get(_url(self.workspace.id))
        assert response.status_code == 200, response.content
        body = response.json()
        assert "results" in body
        assert [row["full_name"] for row in body["results"]] == ["main.sales.orders"]

    def test_submit_approve_reject_round_trip_through_the_real_workflow(self):
        create = _client(self.requester).post(
            _url(self.workspace.id), _create_payload(), format="json"
        )
        request_id = create.json()["id"]

        submit = _client(self.requester).post(_url(self.workspace.id, f"{request_id}/submit/"))
        assert submit.status_code == 200, submit.content
        assert submit.json()["status"] == "PENDING_APPROVAL"

        # The inbox surfaces the pending request for the step approver.
        inbox = _client(self.approver).get("/api/v1/databricks/uc/changes/pending-approvals/")
        assert inbox.status_code == 200
        assert [row["id"] for row in inbox.json()["results"]] == [request_id]

        approve = _client(self.approver).post(_url(self.workspace.id, f"{request_id}/approve/"))
        assert approve.status_code == 200, approve.content
        assert approve.json()["status"] == "APPROVED"

    def test_reject_requires_a_reason_and_records_it(self):
        create = _client(self.requester).post(
            _url(self.workspace.id), _create_payload(), format="json"
        )
        request_id = create.json()["id"]
        _client(self.requester).post(_url(self.workspace.id, f"{request_id}/submit/"))

        reject = _client(self.approver).post(
            _url(self.workspace.id, f"{request_id}/reject/"),
            {"reason": "   "},
            format="json",
        )
        assert reject.status_code == 400

        reject = _client(self.approver).post(
            _url(self.workspace.id, f"{request_id}/reject/"),
            {"reason": "needs a broader review"},
            format="json",
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == "REJECTED"

    def test_comments_and_timeline_endpoints(self):
        create = _client(self.requester).post(
            _url(self.workspace.id), _create_payload(), format="json"
        )
        request_id = create.json()["id"]

        comment = _client(self.requester).post(
            _url(self.workspace.id, f"{request_id}/comments/"),
            {"body": "please review the columns"},
            format="json",
        )
        assert comment.status_code == 201, comment.content

        timeline = _client(self.requester).get(_url(self.workspace.id, f"{request_id}/timeline/"))
        assert timeline.status_code == 200
        kinds = [entry["kind"] for entry in timeline.json()]
        assert "comment" in kinds
        assert "created" in kinds

    def test_cross_tenant_workspace_path_is_404(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_admin = _make_user(
            other_tenant, f"uc-ep-other-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        response = _client(other_admin).get(_url(self.workspace.id))
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(_url(self.workspace.id))
        assert response.status_code == 401

    def test_flag_off_returns_403(self):
        _tenant, requester, _approver, workspace = _seed(flag=False)
        response = _client(requester).get(_url(workspace.id))
        assert response.status_code == 403

    def test_create_with_missing_fields_is_a_clean_400(self):
        # Review hardening: a missing change_type/securable_type must be a
        # clean 400, never a KeyError 500 from the indexing access.
        response = _client(self.requester).post(
            _url(self.workspace.id),
            {"definition": {"identifiers": ["main", "sales", "orders"]}},
            format="json",
        )
        assert response.status_code == 400, response.content

    def test_create_without_identifiers_is_a_clean_400(self):
        # The model's full_clean rejects an empty full_name — the view
        # must surface it as a 400, not a Django-ValidationError 500.
        response = _client(self.requester).post(
            _url(self.workspace.id),
            {
                "change_type": "CREATE",
                "securable_type": "TABLE",
                "definition": {"options": {}},
            },
            format="json",
        )
        assert response.status_code == 400, response.content

    def test_blank_comment_body_is_a_clean_400(self):
        create = _client(self.requester).post(
            _url(self.workspace.id), _create_payload(), format="json"
        )
        request_id = create.json()["id"]
        response = _client(self.requester).post(
            _url(self.workspace.id, f"{request_id}/comments/"),
            {"body": "   "},
            format="json",
        )
        assert response.status_code == 400, response.content

    def test_throttle_scope_enforced_after_burst(self):
        throttled = _make_user(
            self.tenant, f"uc-ep-thr-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        client = _client(throttled)
        for _ in range(30):
            assert client.get(_url(self.workspace.id)).status_code == 200
        assert client.get(_url(self.workspace.id)).status_code == 429
