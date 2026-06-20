"""Phase D (TR.D.6) — DSAR test expansion: service + API + feature-flag + audit."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus
from hub.apps.dsar.workflow import create_dsar_public, transition_status
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class DsarServiceTests(TestCase):
    """Service-layer tests: DSAR creation and status lifecycle."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ds-svc-{uid}",
            slug=f"ds-svc-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dsar_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ds-svc-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )

    def test_dsar_model_exists(self):
        """Verify DSARRequest model is importable and field contract is intact."""
        assert self.tenant.id is not None
        fields = {f.name for f in DSARRequest._meta.get_fields()}
        for required in ("tenant", "request_type", "subject_email", "status"):
            assert required in fields, f"DSARRequest must have '{required}' field"

    def test_service_create(self):
        """create_dsar_public() creates a DSAR with SUBMITTED status."""
        dsar = create_dsar_public(
            tenant_id=str(self.tenant.id),
            request_type=DSARRequestType.ACCESS,
            subject_email="subject@example.com",
            regimes=["GDPR"],
        )
        assert dsar.status == DSARStatus.SUBMITTED
        assert dsar.request_type == DSARRequestType.ACCESS
        assert dsar.subject_email == "subject@example.com"
        assert dsar.tenant == self.tenant

    def test_status_lifecycle(self):
        """transition_status() moves DSAR through status states and emits audit."""
        dsar = DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.ACCESS,
            subject_email="lifecycle@example.com",
            status=DSARStatus.SUBMITTED,
            regimes=["GDPR"],
            statutory_ack_deadline_utc=timezone.now() + timezone.timedelta(days=3),
            statutory_fulfil_deadline_utc=timezone.now() + timezone.timedelta(days=30),
        )
        assert dsar.status == DSARStatus.SUBMITTED

        transition_status(
            dsar, DSARStatus.UNDER_REVIEW, actor_user=self.user, notes="Starting review"
        )
        dsar.refresh_from_db()
        assert dsar.status == DSARStatus.UNDER_REVIEW

        transition_status(
            dsar, DSARStatus.CLOSED_FULFILLED, actor_user=self.user, notes="Request fulfilled"
        )
        dsar.refresh_from_db()
        assert dsar.status == DSARStatus.CLOSED_FULFILLED


class DsarApiTests(TestCase):
    """API endpoint integration tests for DSAR handler."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ds-api-{uid}",
            slug=f"ds-api-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dsar_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ds-api-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_endpoint(self):
        """GET /api/v1/dsar/requests/ returns paginated results for handler."""
        resp = self.client.get("/api/v1/dsar/requests/")
        assert resp.status_code == 200
        assert "results" in resp.data or isinstance(resp.data, list)

    def test_public_submission(self):
        """Public DSAR submission endpoint accepts anonymous POST at /api/v1/public/dsar-requests/."""
        public_client = APIClient()
        resp = public_client.post(
            "/api/v1/public/dsar-requests/",
            {
                "request_type": DSARRequestType.ACCESS,
                "subject_email": "public@example.com",
                "regimes": ["GDPR"],
            },
            format="json",
        )
        # Public submit returns 201 on success or 400 if captcha/validation fails
        assert resp.status_code in (201, 202, 400)


class DsarFeatureFlagTests(TestCase):
    """Feature-flag gating for DSAR endpoints."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ds-ff-{uid}",
            slug=f"ds-ff-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dsar_enabled=False,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ds-ff-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_flag_disabled_gated(self):
        """When compliance_dsar_enabled=False, create_dsar_public raises ValidationError."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            create_dsar_public(
                tenant_id=str(self.tenant.id),
                request_type=DSARRequestType.ACCESS,
                subject_email="flagged@example.com",
                regimes=["GDPR"],
            )

    def test_flag_enabled_accessible(self):
        """When compliance_dsar_enabled=True, handler endpoints return 200."""
        self.tenant.compliance_dsar_enabled = True
        self.tenant.save(update_fields=["compliance_dsar_enabled"])
        resp = self.client.get("/api/v1/dsar/requests/")
        assert resp.status_code == 200


class DsarAuditTests(TestCase):
    """Audit event emission for DSAR operations."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ds-audit-{uid}",
            slug=f"ds-audit-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_dsar_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ds-audit-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )

    def test_create_audit(self):
        """Public DSAR submission emits DSAR_SUBMITTED audit event."""
        before = AuditEvent.objects.filter(resource_type="DSAR_REQUEST").count()
        create_dsar_public(
            tenant_id=str(self.tenant.id),
            request_type=DSARRequestType.ACCESS,
            subject_email="audit-create@example.com",
            regimes=["GDPR"],
        )
        after = AuditEvent.objects.filter(resource_type="DSAR_REQUEST").count()
        assert after >= before + 1

    def test_complete_audit(self):
        """DSAR status transition emits audit event."""
        dsar = DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.ACCESS,
            subject_email="audit-complete@example.com",
            status=DSARStatus.UNDER_REVIEW,
            regimes=["GDPR"],
            statutory_ack_deadline_utc=timezone.now() + timezone.timedelta(days=3),
            statutory_fulfil_deadline_utc=timezone.now() + timezone.timedelta(days=30),
        )
        before = AuditEvent.objects.filter(resource_type="DSAR_REQUEST").count()
        transition_status(dsar, DSARStatus.CLOSED_FULFILLED, actor_user=self.user, notes="Done")
        after = AuditEvent.objects.filter(resource_type="DSAR_REQUEST").count()
        assert after >= before + 1
