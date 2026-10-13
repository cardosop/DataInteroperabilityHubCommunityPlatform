"""TDD pins for the U4 approval UX (openspec add-databricks-uc-write
task 2.8) — DDL preview, timeline + comments, approver inbox,
transition side effects (notifications + webhooks + metrics).

No mocks: real Postgres rows (requests, comments, principals,
notifications, webhook deliveries), the REAL workflow service functions
from uc_changes (submit/approve/reject with step authorization), the
REAL WebhookDeliveryService (a subscribed webhook's delivery row is the
pin; the delivery POST targets the real local HTTP server), and the
metrics record wrappers patched at the MODULE boundary (the 1.10
convention — the transition code path is the real one).
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequest,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed(with_approver=True):
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    requester = _make_user(tenant, f"uc-ux-req-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    requester.status = UserStatus.ACTIVE
    requester.save(update_fields=["status"])
    approver = None
    if with_approver:
        approver = _make_user(tenant, f"uc-ux-app-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        approver.status = UserStatus.ACTIVE
        approver.save(update_fields=["status"])
    workspace = _make_workspace(tenant)
    return tenant, requester, approver, workspace


def _draft_request(tenant, workspace, requester, *, requires_approval=True):
    return UCChangeRequest.objects.create(
        tenant=tenant,
        workspace=workspace,
        requested_by=requester,
        change_type=UCChangeAction.CREATE,
        securable_type=UCObjectType.TABLE,
        full_name="main.sales.orders",
        definition={
            "identifiers": ["main", "sales", "orders"],
            "options": {"table_type": "MANAGED", "columns": [{"name": "id"}]},
        },
        status=UCChangeRequestStatus.DRAFT,
        requires_approval=requires_approval,
        required_approval_chain=[{"step": 1, "role": "TENANT_ADMIN", "label": "Admin step"}],
    )


class TestDdlPreview:
    """The approver sees exactly what will execute — no network."""

    def test_preview_renders_the_rest_pin(self):
        from hub.apps.databricks_admin.uc_change_ux import preview_change

        tenant, requester, _approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        preview = preview_change(request)
        assert preview["kind"] == "rest"
        assert preview["method"] == "POST"
        assert preview["path"] == "/api/2.1/unity-catalog/tables"
        assert preview["body"]["name"] == "orders"
        assert preview["body"]["catalog_name"] == "main"
        assert RecordingHandler.requests == [], "a preview is derived locally — ZERO network"

    def test_preview_renders_the_sql_statement_for_sql_only_types(self):
        from hub.apps.databricks_admin.uc_change_ux import preview_change

        tenant, requester, _approver, workspace = _seed()
        request = UCChangeRequest.objects.create(
            tenant=tenant,
            workspace=workspace,
            requested_by=requester,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.MATERIALIZED_VIEW,
            full_name="main.sales.mv_orders",
            definition={
                "identifiers": ["main", "sales", "mv_orders"],
                "options": {"query": "SELECT 1"},
            },
        )
        preview = preview_change(request)
        assert preview["kind"] == "sql"
        assert "CREATE MATERIALIZED VIEW" in preview["statement"]
        assert "`main`.`sales`.`mv_orders`" in preview["statement"]
        assert RecordingHandler.requests == []

    def test_preview_of_an_unknown_securable_marks_unsupported(self):
        # Review hardening: a deploy-rollback row carries a securable the
        # CURRENT vocabulary does not know — the preview must mark it
        # unsupported, never crash the detail endpoint with ValueError.
        from hub.apps.databricks_admin.uc_change_ux import preview_change

        tenant, requester, _approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        UCChangeRequest.objects.filter(pk=request.pk).update(securable_type="BOGUS_SECURABLE")
        request.refresh_from_db()
        preview = preview_change(request)
        assert preview["kind"] == "unsupported"
        assert RecordingHandler.requests == []

    def test_preview_marks_unsupported_combinations(self):
        from hub.apps.databricks_admin.uc_change_ux import preview_change

        tenant, requester, _approver, workspace = _seed()
        request = UCChangeRequest.objects.create(
            tenant=tenant,
            workspace=workspace,
            requested_by=requester,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.STREAMING_TABLE,
            full_name="main.sales.st_events",
            definition={"identifiers": ["main", "sales", "st_events"]},
        )
        preview = preview_change(request)
        assert preview["kind"] == "unsupported"
        assert RecordingHandler.requests == []


class TestTimelineAndComments:
    def test_timeline_merges_status_events_and_comments_in_order(self):
        from hub.apps.databricks_admin.uc_change_ux import add_comment, timeline_for
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        submit_change_request(change_request=request)
        request.refresh_from_db()
        add_comment(request, approver, "looks fine, proceeding")
        add_comment(request, requester, "thanks!")

        timeline = timeline_for(request)
        kinds = [entry["kind"] for entry in timeline]
        assert kinds[0] == "created"
        assert kinds[1] == "submitted"
        assert kinds[2:] == ["comment", "comment"]
        assert timeline[-2]["body"] == "looks fine, proceeding"
        assert timeline[-2]["author"] == approver.email

    def test_add_comment_rejects_blank_bodies(self):
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.uc_change_ux import add_comment

        tenant, requester, approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        with pytest.raises(ValidationError):
            add_comment(request, approver, "   ")


class TestApprovalInbox:
    """The inbox shows only requests the CURRENT step authorizes me for."""

    def test_inbox_shows_the_current_step_approver_only(self):
        from hub.apps.databricks_admin.uc_change_ux import approval_inbox
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, approver, workspace = _seed()
        stranger = _make_user(tenant, f"uc-ux-str-{uuid.uuid4().hex[:8]}@test.com", None)
        request = _draft_request(tenant, workspace, requester)
        submit_change_request(change_request=request)
        request.refresh_from_db()

        assert list(approval_inbox(approver)) == [request]
        assert list(approval_inbox(stranger)) == []

    def test_inbox_empties_after_approval(self):
        from hub.apps.databricks_admin.uc_change_ux import approval_inbox
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        submit_change_request(change_request=request)
        request.refresh_from_db()
        approve_change_request(change_request=request, approver=approver)
        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.APPROVED
        assert list(approval_inbox(approver)) == []


class TestTransitionSideEffects(TestCase):
    """submit/approve/reject emit notifications + webhooks + metrics."""

    def _submitted(self):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, approver, workspace = _seed()
        request = _draft_request(tenant, workspace, requester)
        submit_change_request(change_request=request)
        request.refresh_from_db()
        return tenant, requester, approver, workspace, request

    def test_submit_notifies_the_step_approver_in_app(self):
        from hub.apps.notifications.models import UserNotification

        tenant, _requester, approver, _workspace, request = self._submitted()
        notes = UserNotification.objects.filter(
            tenant=tenant, user=approver, resource_type="DATABRICKS_UC_CHANGE_REQUEST"
        )
        assert notes.exists(), "the step approver must be notified in-app on submit"
        assert str(request.id) == str(notes.get().resource_id)

    def test_approve_notifies_the_requester_in_app(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request
        from hub.apps.notifications.models import UserNotification

        tenant, requester, _approver, _workspace, request = self._submitted()
        approve_change_request(change_request=request, approver=_approver)
        notes = UserNotification.objects.filter(
            tenant=tenant, user=requester, resource_type="DATABRICKS_UC_CHANGE_REQUEST"
        )
        assert notes.exists(), "the requester must be notified on approval"

    def test_approve_triggers_the_subscribed_webhook_delivery(self):
        import http.server
        import threading

        from hub.apps.databricks_admin.uc_changes import approve_change_request
        from hub.apps.webhooks.models import Webhook, WebhookStatus

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = ["{}"]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)

        tenant, _requester, approver, _workspace, request = self._submitted()
        Webhook.objects.create(
            tenant=tenant,
            name="approval-sink",
            url=f"http://127.0.0.1:{port}/webhook",
            secret="secret",
            event_types=["databricks.uc_change.approved"],
            status=WebhookStatus.ACTIVE,
        )

        approve_change_request(change_request=request, approver=approver)

        from hub.apps.webhooks.models import WebhookDelivery

        deliveries = WebhookDelivery.objects.filter(
            webhook__tenant=tenant, event_type="databricks.uc_change.approved"
        )
        assert deliveries.exists(), "the subscribed webhook must receive the approval event"

    def test_transition_without_subscriptions_triggers_nothing(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request
        from hub.apps.webhooks.models import WebhookDelivery

        tenant, _requester, approver, _workspace, request = self._submitted()
        approve_change_request(change_request=request, approver=approver)
        assert not WebhookDelivery.objects.filter(
            webhook__tenant=tenant, event_type="databricks.uc_change.approved"
        ).exists()

    def test_transitions_record_the_metrics(self):
        from unittest.mock import patch

        from hub.apps.databricks_admin.uc_changes import approve_change_request

        tenant, _requester, approver, _workspace, request = self._submitted()
        with (
            patch("hub.apps.databricks_admin.metrics.record_uc_change_request") as record,
        ):
            approve_change_request(change_request=request, approver=approver)
        record.assert_called_once()
        call = record.call_args
        assert call.args[0] == "approved", "the event rides POSITIONALLY"
        assert call.kwargs["tenant_id"] == str(tenant.id)
