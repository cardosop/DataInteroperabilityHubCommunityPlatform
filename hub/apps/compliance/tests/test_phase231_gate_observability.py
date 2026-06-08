"""
Phase 231.9 — intake / publish gate metrics + Grafana dashboard contract.

Uses real metric wrappers (no patch/stub of business logic).
"""

from __future__ import annotations
import pytest
import pytest

import json
import uuid
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.intake_scan import enqueue_compliance_intake_scan
from hub.apps.compliance.metrics_phase231 import (
    EVENT_SCAN_ENQUEUED,
    record_compliance_intake_gate_event,
)
from hub.apps.observability.otel_metrics import (
    compliance_intake_gate_events_total,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_DASHBOARD = (
    Path(__file__).resolve().parents[4]
    / "monitoring"
    / "grafana"
    / "dashboards"
    / "compliance-intake-gate.json"
)


@pytest.mark.integration
class TestPhase231Metrics(TestCase):
    def setUp(self):
        cache.clear()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Metric tenant {uid}",
            slug=f"metric-231-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_intake_gate_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_record_compliance_intake_gate_event_increments_counter(self):
        labeled = compliance_intake_gate_events_total.labels(
            event=EVENT_SCAN_ENQUEUED,
            tenant_id=str(self.tenant.id),
        )
        before = labeled._value.get()
        record_compliance_intake_gate_event(
            EVENT_SCAN_ENQUEUED,
            self.tenant.id,
        )
        self.assertEqual(labeled._value.get(), before + 1)

    @pytest.mark.integration
    def test_enqueue_intake_scan_increments_metric(self):
        # ``Asset.objects.create`` fires a ``post_save`` signal
        # (``enqueue_compliance_intake_scan_on_asset_created`` in
        # ``compliance/signals.py``) that ALREADY calls
        # ``enqueue_compliance_intake_scan`` for tenants with the
        # gate enabled. The function then sets a 5-minute idempotency
        # cache key per ``(tenant, asset)`` — an explicit second call
        # in the same test returns ``None`` because the cache is
        # already populated. Capture the metric BEFORE asset
        # creation so the signal-driven enqueue is what we measure;
        # the contract under test is "an Asset post-save in a
        # gate-enabled tenant increments the scan-enqueued metric
        # exactly once".
        labeled = compliance_intake_gate_events_total.labels(
            event=EVENT_SCAN_ENQUEUED,
            tenant_id=str(self.tenant.id),
        )
        before = labeled._value.get()
        Asset.objects.create(
            tenant=self.tenant,
            key=f"k-{uuid.uuid4().hex[:6]}",
            name="M",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.assertEqual(labeled._value.get(), before + 1)


@pytest.mark.integration
class TestComplianceIntakeDashboardJson(TestCase):
    EXPECTED_METRICS = frozenset(
        {
            "compliance_intake_gate_events_total",
            "poll_timeout_total",
            "audit_events_total",
        }
    )

    @pytest.mark.integration
    def test_dashboard_is_valid_nested_json(self):
        self.assertTrue(_DASHBOARD.exists(), f"Missing {_DASHBOARD}")
        data = json.loads(_DASHBOARD.read_text())
        self.assertIn("dashboard", data)
        self.assertEqual(
            data["dashboard"]["uid"],
            "compliance-intake-gate-231",
        )

    @pytest.mark.integration
    def test_dashboard_queries_reference_known_metrics(self):
        data = json.loads(_DASHBOARD.read_text())
        panels = data["dashboard"]["panels"]
        exprs = []
        for panel in panels:
            for target in panel.get("targets", []):
                ex = target.get("expr", "")
                if ex:
                    exprs.append(ex)
        for expr in exprs:
            self.assertTrue(
                any(m in expr for m in self.EXPECTED_METRICS),
                f"Query references no known metric: {expr!r}",
            )
