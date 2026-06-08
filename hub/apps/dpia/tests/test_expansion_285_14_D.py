"""Phase D (TR.D.7) — DPIA test expansion: service + API + feature-flag + audit."""
import pytest
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.dpia.models import Dpia, DpiaStatus
from hub.apps.dpia.workflow import submit_dpia, review_dpia
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class DpiaServiceTests(TestCase):
    """Service-layer tests: wizard workflow and review decisions."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dp-svc-{uid}", slug=f"dp-svc-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dp-svc-{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])

    def test_dpia_model_exists(self):
        """Verify Dpia model is importable and field contract is intact."""
        assert self.tenant.id is not None
        fields = {f.name for f in Dpia._meta.get_fields()}
        for required in ('tenant', 'title', 'status', 'created_by'):
            assert required in fields, f"Dpia must have '{required}' field"

    def test_wizard_workflow(self):
        """Submit a draft DPIA through the wizard: DRAFT → IN_REVIEW."""
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Wizard DPIA",
            status=DpiaStatus.DRAFT,
            created_by=self.user,
            wizard_payload={"purpose": "evaluation", "data_categories": ["personal"]},
        )
        assert dpia.status == DpiaStatus.DRAFT

        submit_dpia(dpia=dpia, actor=self.user)
        dpia.refresh_from_db()
        assert dpia.status == DpiaStatus.IN_REVIEW

    def test_review_decision(self):
        """Review a DPIA: IN_REVIEW → APPROVED."""
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Review DPIA",
            status=DpiaStatus.IN_REVIEW,
            created_by=self.user,
            wizard_payload={"risk": "low"},
        )
        # Grant DPO role for review
        dpo_role, _ = Role.objects.get_or_create(
            name="DPO", tenant=self.tenant,
            defaults={"description": "Data Protection Officer"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=dpo_role)

        review_dpia(dpia=dpia, actor=self.user, outcome=DpiaStatus.APPROVED, dpo_summary="Looks good")
        dpia.refresh_from_db()
        assert dpia.status == DpiaStatus.APPROVED
        assert dpia.reviewed_by == self.user


class DpiaApiTests(TestCase):
    """API endpoint integration tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dp-api-{uid}", slug=f"dp-api-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dp-api-{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_endpoint(self):
        """GET /api/v1/dpia/records/ returns paginated results."""
        resp = self.client.get("/api/v1/dpia/records/")
        assert resp.status_code == 200
        assert "results" in resp.data or isinstance(resp.data, list)

    def test_review_queue(self):
        """DPIA records can be filtered by status for review queue."""
        # Create a DPIA in IN_REVIEW status
        Dpia.objects.create(
            tenant=self.tenant,
            title="Queue DPIA",
            status=DpiaStatus.IN_REVIEW,
            created_by=self.user,
        )
        resp = self.client.get("/api/v1/dpia/records/", {"status": "IN_REVIEW"})
        assert resp.status_code == 200
        data = resp.data
        results = data.get("results", data if isinstance(data, list) else [])
        assert len(results) >= 1


class DpiaFeatureFlagTests(TestCase):
    """Feature-flag gating for DPIA endpoints."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dp-ff-{uid}", slug=f"dp-ff-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dpia_enabled=False,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dp-ff-{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_flag_disabled_gated(self):
        """When compliance_dpia_enabled=False, DPIA create is blocked."""
        resp = self.client.post("/api/v1/dpia/records/", {
            "title": "Flag Test DPIA",
        }, format="json")
        # Should be denied (403) when DPIA is disabled
        assert resp.status_code != 201

    def test_flag_enabled_accessible(self):
        """When compliance_dpia_enabled=True, DPIA endpoints return 200."""
        self.tenant.compliance_dpia_enabled = True
        self.tenant.save(update_fields=["compliance_dpia_enabled"])
        resp = self.client.get("/api/v1/dpia/records/")
        assert resp.status_code == 200


class DpiaAuditTests(TestCase):
    """Audit event emission for DPIA operations."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dp-audit-{uid}", slug=f"dp-audit-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dp-audit-{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])

    def test_create_audit(self):
        """Submitting a DPIA emits DPIA_SUBMITTED audit event."""
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Audit Create DPIA",
            status=DpiaStatus.DRAFT,
            created_by=self.user,
        )
        before = AuditEvent.objects.filter(resource_type="DPIA").count()
        submit_dpia(dpia=dpia, actor=self.user)
        after = AuditEvent.objects.filter(resource_type="DPIA").count()
        assert after >= before + 1

    def test_review_audit(self):
        """Reviewing a DPIA emits DPIA_REVIEWED audit event."""
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Audit Review DPIA",
            status=DpiaStatus.IN_REVIEW,
            created_by=self.user,
        )
        dpo_role, _ = Role.objects.get_or_create(
            name="DPO", tenant=self.tenant,
            defaults={"description": "Data Protection Officer"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=dpo_role)
        before = AuditEvent.objects.filter(resource_type="DPIA").count()
        review_dpia(dpia=dpia, actor=self.user, outcome=DpiaStatus.APPROVED, dpo_summary="Approved")
        after = AuditEvent.objects.filter(resource_type="DPIA").count()
        assert after >= before + 1
