"""Phase D (TR.D.5) — Breach test expansion: service + API + feature-flag + audit."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.breach.models import BreachIncident, BreachIncidentStatus, BreachNotificationStatus
from hub.apps.breach.workflow import (
    create_breach_incident,
    mark_notification_sent,
    transition_incident_status,
)
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class BreachServiceTests(TestCase):
    """Service-layer tests: incident creation and notification workflow."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"br-svc-{uid}",
            slug=f"br-svc-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_breach_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"br-svc-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)

    def test_breach_model_exists(self):
        """Verify BreachIncident model is importable and field contract is intact."""
        self.assertIsNotNone(self.tenant.id)

        fields = {f.name for f in BreachIncident._meta.get_fields()}
        for required in ("tenant", "title", "status", "discovered_at"):
            self.assertIn(required, fields,
                          f"BreachIncident must have '{required}' field")

    def test_service_create(self):
        """create_breach_incident() creates incident + notifications + audit."""
        regimes = ["GDPR"]
        incident = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Service-created breach",
            summary="Test via service layer",
            regimes=regimes,
            discovered_at=timezone.now(),
        )
        self.assertEqual(incident.status, BreachIncidentStatus.OPEN)
        self.assertEqual(incident.tenant, self.tenant)
        self.assertEqual(incident.title, "Service-created breach")
        self.assertEqual(incident.regimes, regimes)
        # Notifications are spawned per regime
        self.assertGreaterEqual(incident.notifications.count(), len(regimes))

    def test_notification_workflow(self):
        """mark_notification_sent() transitions notification + records proof hash."""
        regimes = ["GDPR"]
        incident = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Workflow breach",
            summary="Notification workflow test",
            regimes=regimes,
            discovered_at=timezone.now(),
        )
        notification = incident.notifications.first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.status, BreachNotificationStatus.PENDING)

        mark_notification_sent(
            notification=notification,
            actor=self.user,
            outbound_reference="REF-001",
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, BreachNotificationStatus.SENT)
        self.assertEqual(notification.outbound_reference, "REF-001")
        self.assertEqual(len(notification.delivery_proof_sha256), 64)


class BreachApiTests(TestCase):
    """API endpoint integration tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"br-api-{uid}",
            slug=f"br-api-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_breach_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"br-api-{uid}@test.local",
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
        """GET /api/v1/breach/incidents/ returns paginated results."""
        resp = self.client.get("/api/v1/breach/incidents/")
        self.assertEqual(resp.status_code, 200)
        # Should return a paginated response structure
        self.assertTrue("results" in resp.data or isinstance(resp.data, list))

    def test_permission_checks(self):
        """Non-responder user gets 403 on breach endpoints."""
        # Create a user without TENANT_ADMIN/DPO/SECURITY_ADMIN role
        uid = uuid.uuid4().hex[:8]
        plain_user = User.objects.create_user(
            email=f"plain-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        plain_client = APIClient()
        plain_client.force_authenticate(user=plain_user)
        resp = plain_client.get("/api/v1/breach/incidents/")
        self.assertEqual(resp.status_code, 403)


class BreachFeatureFlagTests(TestCase):
    """Feature-flag gating tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"br-ff-{uid}",
            slug=f"br-ff-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_breach_enabled=False,  # disabled by default for this test class
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"br-ff-{uid}@test.local",
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
        """When compliance_breach_enabled=False, breach create is blocked."""
        resp = self.client.post(
            "/api/v1/breach/incidents/",
            {
                "title": "Flag test breach",
                "summary": "Testing flag gating",
                "regimes": ["GDPR"],
                "discovered_at": timezone.now().isoformat(),
            },
            format="json",
        )
        # Should be denied with 403 when breach workflow is disabled
        self.assertEqual(resp.status_code, 403,
                         f"Expected 403, got {resp.status_code}: {resp.data}")
        self.assertIn("error", resp.data)
        self.assertIn("disabled", resp.data["error"].lower())

    def test_flag_enabled_accessible(self):
        """When compliance_breach_enabled=True, breach endpoints return 200."""
        self.tenant.compliance_breach_enabled = True
        self.tenant.save(update_fields=["compliance_breach_enabled"])
        resp = self.client.get("/api/v1/breach/incidents/")
        self.assertEqual(resp.status_code, 200)


class BreachAuditTests(TestCase):
    """Audit event emission tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"br-audit-{uid}",
            slug=f"br-audit-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_breach_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"br-audit-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)

    def test_create_audit(self):
        """Creating a breach incident emits BREACH_INCIDENT_OPENED audit."""
        before = AuditEvent.objects.filter(
            resource_type="BREACH_INCIDENT",
            action="BREACH_INCIDENT_OPENED",
        ).count()
        create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Audit test breach",
            summary="Verify audit on create",
            regimes=["GDPR"],
            discovered_at=timezone.now(),
        )
        after = AuditEvent.objects.filter(
            resource_type="BREACH_INCIDENT",
            action="BREACH_INCIDENT_OPENED",
        ).count()
        self.assertEqual(after, before + 1)

    def test_update_audit(self):
        """Transitioning incident status emits BREACH_INCIDENT_STATUS_CHANGED audit."""
        incident = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Audit update test",
            summary="Verify audit on update",
            regimes=["GDPR"],
            discovered_at=timezone.now(),
        )
        before = AuditEvent.objects.filter(
            resource_type="BREACH_INCIDENT",
            action="BREACH_INCIDENT_STATUS_CHANGED",
        ).count()
        transition_incident_status(
            incident=incident,
            actor=self.user,
            new_status=BreachIncidentStatus.CONTAINED,
            notes="Contained after investigation",
        )
        after = AuditEvent.objects.filter(
            resource_type="BREACH_INCIDENT",
            action="BREACH_INCIDENT_STATUS_CHANGED",
        ).count()
        self.assertEqual(after, before + 1)
