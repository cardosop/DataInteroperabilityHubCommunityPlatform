"""
Phase 250.6.C TDD pin for the asset-creation workflow-status endpoint.

The frontend's ``WorkflowProgressWidget`` polls
``GET /api/v1/assets/workflows/{workflow_instance_id}/status/`` to
render step + progress + ETA on the asset detail page during the
RUNNING phase. Tests pin the wire contract end-to-end:

* Tenant-scoped: cross-tenant lookups MUST return 404 (existence-leak
  protection — same posture as the IDOR gate from Phase 250.5.C).
* Malformed UUIDs MUST return 404 (NOT 400 — preserves zero-knowledge
  about which UUIDs map to existing rows).
* RUNNING workflow returns ``status="RUNNING"`` + ``progress_percentage``
  + ``current_step_name`` + ``started_at`` (the FE uses ``started_at``
  to apply the F2-4 polling backoff after 30s of RUNNING).
* COMPLETED workflow returns ``status="COMPLETED"`` + ``asset_id``.
* PENDING (DRAFT internal status) returns ``status="PENDING"``.
* FAILED returns ``status="FAILED"`` + a message.

Tests use real Django ORM rows + real DRF APIClient — no mocks. The
WorkflowInstance is created directly via ``WorkflowInstance.objects.create``
(no full workflow execution) so the test exercises only the read
endpoint's mapping logic.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_data_provider_role,
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant(*, slug_prefix: str = "t"):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    ensure_user_has_tenant_admin_role(user)
    return tenant, user


def _seed_workflow_instance(
    tenant,
    user,
    *,
    status: str = WorkflowStatus.RUNNING,
    progress: int = 50,
    step_name: str = "validate_contract",
    asset_id: str | None = None,
    error_message: str | None = None,
):
    wf_def = WorkflowDefinition.objects.create(
        name="asset_creation_test",
        version="2.0.0",
        dsl_json={
            "version": "2.0.0",
            "steps": [{"name": "validate_contract", "type": "validation"}],
        },
        is_active=True,
        created_by=user,
    )
    state = {
        "progress_percentage": progress,
        "current_step_name": step_name,
    }
    if asset_id:
        state["asset_id"] = asset_id
    if error_message:
        state["error_message"] = error_message
    return WorkflowInstance.objects.create(
        workflow_definition=wf_def,
        workflow_name="asset_creation_test",
        workflow_version="2.0.0",
        tenant=tenant,
        status=status,
        input_data={},
        state_data=state,
        created_by=user,
    )


class AssetWorkflowStatusRunningTest(TestCase):
    """RUNNING workflow returns full status payload incl.
    progress + step + started_at (the FE uses started_at to apply
    the F2-4 polling backoff after 30s of RUNNING)."""

    def test_running_returns_progress_step_started_at(self):
        tenant, user = _seed_tenant()
        wi = _seed_workflow_instance(
            tenant, user,
            status=WorkflowStatus.RUNNING,
            progress=42,
            step_name="run_compliance_checks",
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            f"/api/v1/assets/workflows/{wi.id}/status/"
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["workflow_instance_id"] == str(wi.id)
        assert body["status"] == "RUNNING"
        assert body["progress_percentage"] == 42
        assert body["current_step_name"] == "run_compliance_checks"
        assert body["started_at"] is not None  # ISO-8601 string
        assert body["asset_id"] is None  # not set on this RUNNING instance


class AssetWorkflowStatusCompletedTest(TestCase):
    """COMPLETED workflow returns ``status=COMPLETED`` + ``asset_id``."""

    def test_completed_returns_asset_id(self):
        tenant, user = _seed_tenant()
        asset_uuid = str(uuid.uuid4())
        wi = _seed_workflow_instance(
            tenant, user,
            status=WorkflowStatus.COMPLETED,
            progress=100,
            step_name="activate_asset",
            asset_id=asset_uuid,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            f"/api/v1/assets/workflows/{wi.id}/status/"
        )
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["asset_id"] == asset_uuid
        assert body["progress_percentage"] == 100


class AssetWorkflowStatusFailedTest(TestCase):
    """FAILED workflow returns ``status=FAILED`` + error message."""

    def test_failed_returns_error_message(self):
        tenant, user = _seed_tenant()
        wi = _seed_workflow_instance(
            tenant, user,
            status=WorkflowStatus.FAILED,
            progress=30,
            step_name="run_dq_checks",
            error_message="DQ check failed: bad data",
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            f"/api/v1/assets/workflows/{wi.id}/status/"
        )
        body = resp.json()
        assert body["status"] == "FAILED"
        assert "DQ check failed" in body["message"]


class AssetWorkflowStatusPendingTest(TestCase):
    """DRAFT internal status maps to API ``PENDING``."""

    def test_draft_maps_to_pending(self):
        tenant, user = _seed_tenant()
        wi = _seed_workflow_instance(
            tenant, user,
            status=WorkflowStatus.DRAFT,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            f"/api/v1/assets/workflows/{wi.id}/status/"
        )
        body = resp.json()
        assert body["status"] == "PENDING"


class AssetWorkflowStatusTenantScopingTest(TestCase):
    """Cross-tenant + malformed UUID lookups return 404 (existence-leak
    protection — mirrors the Phase 250.5.C IDOR contract)."""

    def test_cross_tenant_returns_404(self):
        tenant_a, _user_a = _seed_tenant(slug_prefix="a")
        _tenant_b, user_b = _seed_tenant(slug_prefix="b")
        wi_a = _seed_workflow_instance(tenant_a, _user_a)

        client = APIClient()
        client.force_authenticate(user=user_b)
        resp = client.get(
            f"/api/v1/assets/workflows/{wi_a.id}/status/"
        )
        assert resp.status_code == 404, resp.content

    def test_malformed_uuid_returns_404(self):
        _tenant, user = _seed_tenant()
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/assets/workflows/not-a-uuid/status/")
        # 404 (NOT 400) — preserves zero-knowledge about UUID validity.
        assert resp.status_code == 404, resp.content
