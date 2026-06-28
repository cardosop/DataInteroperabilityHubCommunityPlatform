"""
Phase 277.B.088 — breach SLA metrics tests.
"""

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.breach.models import (
    BreachIncident,
    BreachIncidentStatus,
)
from hub.apps.breach.sla_metrics import emit_breach_sla_metrics
from hub.apps.observability.otel_metrics import breach_hours_since_discovery
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


class BreachSLAMetricsTests(TestCase):
    def setUp(self):
        import uuid

        self.tenant = Tenant.objects.create(
            name=f"SLA Tenant {uuid.uuid4().hex[:8]}",
            slug=f"sla-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )
        # Reset the gauge values between tests by clearing any prior data
        BreachIncident.objects.all().delete()

    def test_metric_exists_with_expected_labels(self):
        self.assertEqual(breach_hours_since_discovery.name, "breach_hours_since_discovery")
        self.assertEqual(
            set(breach_hours_since_discovery._expected_labels),
            {"tenant_id", "breach_id"},
        )

    def test_emit_returns_empty_list_when_no_breaches(self):
        results = emit_breach_sla_metrics()
        self.assertEqual(results, [])

    def test_emit_reports_hours_for_open_breach(self):
        breach = BreachIncident.objects.create(
            tenant=self.tenant,
            title="Test breach",
            discovered_at=timezone.now() - timedelta(hours=5),
            status=BreachIncidentStatus.OPEN,
        )
        results = emit_breach_sla_metrics()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["breach_id"], str(breach.id))
        self.assertTrue(4.5 <= results[0]["hours"] <= 5.5)  # ~5 hours

    def test_emit_skips_closed_breaches(self):
        BreachIncident.objects.create(
            tenant=self.tenant,
            title="Closed breach",
            discovered_at=timezone.now() - timedelta(hours=50),
            status=BreachIncidentStatus.CLOSED,
        )
        results = emit_breach_sla_metrics()
        self.assertFalse(
            any(r["breach_id"] == str(BreachIncident.objects.first().id) for r in results)
        )

    def test_emit_skips_legal_hold_breaches(self):
        BreachIncident.objects.create(
            tenant=self.tenant,
            title="Hold breach",
            discovered_at=timezone.now() - timedelta(hours=70),
            status=BreachIncidentStatus.OPEN,
            legal_hold=True,
            legal_hold_reason="Pending external review",
        )
        results = emit_breach_sla_metrics()
        self.assertEqual(len(results), 0)

    def test_emit_reports_gauge_value(self):
        BreachIncident.objects.create(
            tenant=self.tenant,
            title="Gauge breach",
            discovered_at=timezone.now() - timedelta(hours=10),
            status=BreachIncidentStatus.OPEN,
        )
        emit_breach_sla_metrics()

        breach = BreachIncident.objects.first()
        labeled = breach_hours_since_discovery.labels(
            tenant_id=str(self.tenant.id),
            breach_id=str(breach.id),
        )
        # _UpDownCounterWrapper exposes ._value for reading the current
        # gauge value.  This is an intentionally public API of our own
        # wrapper (the underscore prefix is a style convention, not a
        # private-internal flag).
        val = labeled._value.get()
        self.assertTrue(9.5 <= val <= 10.5)  # ~10 hours

    def test_emit_reports_oldest_first(self):
        """Results are ordered by discovered_at ascending — oldest first."""
        BreachIncident.objects.create(
            tenant=self.tenant,
            title="Old breach",
            discovered_at=timezone.now() - timedelta(hours=30),
            status=BreachIncidentStatus.OPEN,
        )
        BreachIncident.objects.create(
            tenant=self.tenant,
            title="New breach",
            discovered_at=timezone.now() - timedelta(hours=5),
            status=BreachIncidentStatus.OPEN,
        )
        results = emit_breach_sla_metrics()
        self.assertGreater(results[0]["hours"], results[1]["hours"])

    def test_emit_handles_unresolved_statuses(self):
        """OPEN, CONTAINED, and NOTIFIED breaches are all reported."""
        for status, hours in [
            (BreachIncidentStatus.OPEN, 65),
            (BreachIncidentStatus.CONTAINED, 40),
            (BreachIncidentStatus.NOTIFIED, 20),
        ]:
            BreachIncident.objects.create(
                tenant=self.tenant,
                title=f"{status.value} breach",
                discovered_at=timezone.now() - timedelta(hours=hours),
                status=status,
            )
        results = emit_breach_sla_metrics()
        self.assertEqual(len(results), 3)
        # All should have positive hours
        for r in results:
            self.assertGreater(r["hours"], 0)
