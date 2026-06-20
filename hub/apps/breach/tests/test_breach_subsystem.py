"""Integration tests for breach workflow (no mocks; real DB + storage path)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.breach.models import (
    BreachIncidentStatus,
    BreachNotification,
    BreachNotificationStatus,
)
from hub.apps.breach.sla_scan import run_breach_notification_clock_scan
from hub.apps.breach.workflow import create_breach_incident, mark_notification_sent
from hub.apps.regulation_policies.registry import breach_statutory_clock_matrix
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


class BreachWorkflowTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="b1",
            slug="b1-" + uuid.uuid4().hex[:8],
            compliance_breach_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"br-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026!",
            tenant=self.tenant,
            display_name="Security",
            status=UserStatus.ACTIVE,
        )
        role = Role.objects.create(tenant=self.tenant, name="SECURITY_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=role)

    @pytest.mark.integration
    def test_create_incident_spawns_notifications_and_audit(self):
        from django.utils import timezone

        inc = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Test breach",
            summary="Summary line",
            regimes=["GDPR"],
            discovered_at=timezone.now(),
        )
        self.assertEqual(inc.status, BreachIncidentStatus.OPEN)
        self.assertGreaterEqual(BreachNotification.objects.filter(incident=inc).count(), 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_id=str(inc.id),
                action="BREACH_INCIDENT_OPENED",
            ).exists()
        )

    @pytest.mark.integration
    def test_per_regime_notification_deadlines(self):
        from django.utils import timezone

        discovered = timezone.now()
        inc = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Multi regime",
            summary="",
            regimes=["GDPR", "CCPA"],
            discovered_at=discovered,
        )
        g_h = int(breach_statutory_clock_matrix("GDPR")["supervisory_notification_hours"])
        c_h = int(breach_statutory_clock_matrix("CCPA")["supervisory_notification_hours"])
        self.assertEqual(
            inc.statutory_authority_deadline_utc,
            discovered + timedelta(hours=min(g_h, c_h)),
        )
        for n in BreachNotification.objects.filter(incident=inc):
            if n.regime == "GDPR":
                self.assertEqual(n.statutory_due_at_utc, discovered + timedelta(hours=g_h))
            elif n.regime == "CCPA":
                self.assertEqual(n.statutory_due_at_utc, discovered + timedelta(hours=c_h))

    @override_settings(USE_S3=False)
    @pytest.mark.integration
    def test_mark_sent_records_proof_hash(self):
        from django.utils import timezone

        inc = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Proof test",
            summary="x",
            regimes=["GDPR"],
            discovered_at=timezone.now(),
        )
        note = BreachNotification.objects.filter(incident=inc).first()
        self.assertIsNotNone(note)
        note = BreachNotification.objects.get(pk=note.id)
        mark_notification_sent(
            note,
            actor=self.user,
            outbound_reference="TICKET-123",
        )
        note.refresh_from_db()
        self.assertEqual(note.status, BreachNotificationStatus.SENT)
        self.assertEqual(len(note.delivery_proof_sha256), 64)
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_id=str(note.id),
                action="BREACH_NOTIFICATION_SENT",
            ).exists()
        )


class BreachApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="b2",
            slug="b2-" + uuid.uuid4().hex[:8],
            compliance_breach_enabled=True,
        )
        # Phase 25.2.4 ``TenantSuspensionMiddleware`` rejects all
        # writes (POST/PUT/PATCH/DELETE) with 403 when the tenant has
        # no ACTIVE subscription. The breach POST below is a write.
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"br2-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026!",
            tenant=self.tenant,
            display_name="Admin",
            status=UserStatus.ACTIVE,
        )
        role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=role)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.integration
    def test_report_breach_endpoint(self):
        from django.utils import timezone

        url = "/api/v1/breach/incidents/"
        resp = self.client.post(
            url,
            {
                "title": "API breach",
                "summary": "via API",
                "regimes": ["GDPR"],
                "discovered_at": timezone.now().isoformat(),
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", resp.data)

    @pytest.mark.integration
    def test_dashboard_lists_incident(self):
        from django.utils import timezone

        create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Dash",
            summary="",
            regimes=["GDPR"],
            discovered_at=timezone.now(),
        )
        r = self.client.get(
            "/api/v1/breach/dashboard/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data["open_incidents_count"], 1)


class BreachSlaScanTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="b3",
            slug="b3-" + uuid.uuid4().hex[:8],
            compliance_breach_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"br3-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026!",
            tenant=self.tenant,
            display_name="DPO",
            status=UserStatus.ACTIVE,
        )
        role = Role.objects.create(tenant=self.tenant, name="DPO", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=role)

    @pytest.mark.integration
    def test_sla_scan_escalates_past_deadline(self):
        from datetime import timedelta

        from django.utils import timezone

        inc = create_breach_incident(
            tenant=self.tenant,
            actor=self.user,
            title="Late",
            summary="",
            regimes=["GDPR"],
            discovered_at=timezone.now() - timedelta(days=10),
        )
        inc.statutory_authority_deadline_utc = timezone.now() - timedelta(hours=1)
        inc.save(update_fields=["statutory_authority_deadline_utc"])
        counters = run_breach_notification_clock_scan()
        self.assertGreaterEqual(counters.get("escalated", 0), 1)
