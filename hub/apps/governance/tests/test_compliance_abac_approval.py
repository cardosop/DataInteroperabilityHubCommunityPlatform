"""
Phase 272.2 + 272.3 — compliance gate + ABAC approval tests.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _mk_tenant(slug=None):
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    s = slug or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"CG-{s}",
        slug=f"cg-{s}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant, email_pfx="user"):
    return User.objects.create_user(
        email=f"{email_pfx}-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_asset(tenant, created_by):
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:8]}",
        name="Test Asset",
        status=AssetStatus.ACTIVE,
        created_by=created_by,
    )


def _mk_ar(tenant, requested_by, asset):
    return AccessRequest.objects.create(
        tenant=tenant,
        requested_by=requested_by,
        asset=asset,
        reason="Test",
        requested_access_type="READ",
        status=AccessRequestStatus.PENDING,
    )


def _make_admin(tenant, user):
    """Grant TENANT_ADMIN role to a user."""
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant Administrator"},
    )
    UserRole.objects.get_or_create(user=user, role=role, tenant=tenant)


def _get_json(resp):
    """Safely extract JSON from a response."""
    if hasattr(resp, "data"):
        return resp.data
    if hasattr(resp, "render"):
        resp.render()
    return json.loads(resp.content)


# ===========================================================================
# 272.2 — Compliance gate
# ===========================================================================


class TestComplianceGate(TestCase):
    """Compliance gate blocks approval when allowed_to_store is not True."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.requester = _mk_user(self.tenant, "req")
        self.approver = _mk_user(self.tenant, "approver")
        _make_admin(self.tenant, self.approver)
        self.asset = _mk_asset(self.tenant, self.requester)
        self.ar = _mk_ar(self.tenant, self.requester, self.asset)
        # Enable compliance gate.
        self.tenant.access_request_compliance_gate_enabled = True
        self.tenant.save(update_fields=["access_request_compliance_gate_enabled"])
        self.client.force_authenticate(user=self.approver)

    def test_blocks_when_no_compliance_run(self):
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 422, _get_json(resp)
        assert "compliance" in str(_get_json(resp)).lower()

    def test_blocks_when_allowed_to_store_false(self):
        from hub.apps.compliance.models import ComplianceRun

        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="SUCCEEDED",
            allowed_to_store=False,
        )
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 422, _get_json(resp)
        assert "compliance" in str(_get_json(resp)).lower()

    def test_approval_proceeds_when_allowed_to_store_true(self):
        from hub.apps.compliance.models import ComplianceRun

        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="SUCCEEDED",
            allowed_to_store=True,
        )
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 200, _get_json(resp)
        self.ar.refresh_from_db()
        assert self.ar.status == AccessRequestStatus.APPROVED

    def test_gate_disabled_flag_preserves_current_behavior(self):
        self.tenant.access_request_compliance_gate_enabled = False
        self.tenant.save(update_fields=["access_request_compliance_gate_enabled"])
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 200, _get_json(resp)
        self.ar.refresh_from_db()
        assert self.ar.status == AccessRequestStatus.APPROVED


class TestForceApproveBypass(TestCase):
    """PLATFORM_ADMIN can override with ?force_approve=true."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.requester = _mk_user(self.tenant, "req")
        self.approver = _mk_user(self.tenant, "approver")
        # Grant TENANT_ADMIN role so the user can approve.
        _make_admin(self.tenant, self.approver)
        # Make them PLATFORM_ADMIN for force_approve tests.
        self.approver.is_platform_admin = True
        self.approver.save()
        self.asset = _mk_asset(self.tenant, self.requester)
        self.ar = _mk_ar(self.tenant, self.requester, self.asset)
        self.tenant.access_request_compliance_gate_enabled = True
        self.tenant.save(update_fields=["access_request_compliance_gate_enabled"])
        self.client.force_authenticate(user=self.approver)

    def test_force_approve_bypasses_compliance_gate(self):
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/?force_approve=true",
            data={},
            format="json",
        )
        data = _get_json(resp)
        assert resp.status_code == 200, data
        self.ar.refresh_from_db()
        assert self.ar.status == AccessRequestStatus.APPROVED

    def test_force_approve_emits_override_audit(self):
        from hub.apps.audit.event_types import ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN
        from hub.apps.audit.models import AuditEvent

        self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/?force_approve=true",
            data={},
            format="json",
        )
        assert AuditEvent.objects.filter(
            action=ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN,
        ).exists()

    def test_non_platform_admin_cannot_force_approve(self):
        self.approver.is_platform_admin = False
        self.approver.save()
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/?force_approve=true",
            data={},
            format="json",
        )
        # force_approve is ignored for non-PLATFORM_ADMIN → blocked by gate.
        assert resp.status_code == 422, _get_json(resp)


# ===========================================================================
# 272.3 — ABAC into approval path
# ===========================================================================


class TestABACApproval(TestCase):
    """ABAC evaluation is called during approval and PERMIT/DENY honoured."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.requester = _mk_user(self.tenant, "req")
        self.approver = _mk_user(self.tenant, "approver")
        _make_admin(self.tenant, self.approver)
        self.asset = _mk_asset(self.tenant, self.requester)
        self.ar = _mk_ar(self.tenant, self.requester, self.asset)
        # Disable compliance gate for ABAC-only tests.
        self.client.force_authenticate(user=self.approver)

    def test_permit_no_policy_approves(self):
        """When no ABAC policy matches, default-deny is NOT applied to
        approval — the approver is a TENANT_ADMIN, so approval proceeds."""
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 200, _get_json(resp)
        self.ar.refresh_from_db()
        assert self.ar.status == AccessRequestStatus.APPROVED

    def test_deny_policy_blocks_approval(self):
        from hub.apps.governance.models import AccessPolicy

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Block all approvals",
            conditions={
                "user": {"roles": ["TENANT_ADMIN"]},
            },
            effect="DENY",
            asset=self.asset,
            priority=1,
        )
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.ar.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 403, _get_json(resp)
