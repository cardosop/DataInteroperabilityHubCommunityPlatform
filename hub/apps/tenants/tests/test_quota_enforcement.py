"""
Quota enforcement boundary-condition tests.

Covers limit keys and edge cases not exercised by
test_plan_limit_service.py or test_plan_limit_enforcement_integration.py:
storage GB conversion, ML plan routing, batch delta, and zero-limit
scenarios.

All tests call ``PlanLimitService.check_limit()`` directly with real DB
resources — no mocks at the enforcement boundary.
"""
from __future__ import annotations

import uuid

import pytest
from django.db import transaction
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.services.base import ValidationError
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantPlan, PlanTier
from hub.apps.tenants.services import PlanLimitService

pytestmark = pytest.mark.django_db(transaction=True)


class QuotaEnforcementTests(TestCase):
    """Boundary-condition quota enforcement tests.

    Each test creates real resources and verifies that
    ``PlanLimitService.check_limit()`` correctly enforces the limit.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.plan = TenantPlan.objects.create(
            name=f"Limit Plan {uid}",
            slug=f"limit-plan-{uid}",
            tier=PlanTier.PRO,
            is_active=True,
            limits_json={
                "max_assets": 10,
                "max_ml_models": 5,
                "max_storage_gb": 2,
            },
        )
        self.tenant = Tenant.objects.create(
            name=f"QuotaTenant {uid}",
            slug=f"quota-{uid}",
            status="ACTIVE",
            plan=self.plan,
        )
        self.service = PlanLimitService(
            tenant_id=str(self.tenant.id), user_id=None,
        )

    # ── Storage GB conversion ──────────────────────────────────────────

    def test_storage_limit_exceeded_with_gb_conversion(self):
        """max_storage_gb blocks writes when total exceeds plan limit."""
        # 5 files × 512 MB each = 2.5 GB > 2 GB plan limit.
        for i in range(5):
            File.objects.create(
                tenant=self.tenant,
                name=f"over-limit-{i}.csv",
                content_type="text/csv",
                size=536_870_912,
                storage_path=f"quota/over-{i}.csv",
                status=FileStatus.ACTIVE,
            )

        with transaction.atomic():
            with pytest.raises(ValidationError) as exc_info:
                self.service.check_limit(
                    str(self.tenant.id), "max_storage_gb", delta=0,
                )
        self.assertEqual(exc_info.value.code, "plan_limit_exceeded")
        details = exc_info.value.details
        self.assertEqual(details["limit_key"], "max_storage_gb")
        self.assertEqual(details["max"], 2)
        self.assertGreater(details["new_usage"], 2)

    def test_storage_limit_within_budget_allows(self):
        """max_storage_gb allows writes when total is under plan limit."""
        # 2 files × 512 MB = 1 GB < 2 GB plan limit.
        for i in range(2):
            File.objects.create(
                tenant=self.tenant,
                name=f"within-{i}.csv",
                content_type="text/csv",
                size=536_870_912,
                storage_path=f"quota/within-{i}.csv",
                status=FileStatus.ACTIVE,
            )

        with transaction.atomic():
            result = self.service.check_limit(
                str(self.tenant.id), "max_storage_gb", delta=0,
            )
        self.assertTrue(result["allowed"])
        self.assertGreaterEqual(result["remaining"], 0)

    # ── ML plan routing ────────────────────────────────────────────────

    def test_ml_key_without_ml_plan_returns_zero(self):
        """Tenant without ml_plan has max=0 for ML limit keys."""
        self.assertIsNone(self.tenant.ml_plan)

        with transaction.atomic():
            with pytest.raises(ValidationError) as exc_info:
                self.service.check_limit(
                    str(self.tenant.id), "max_ml_models", delta=1,
                )
        self.assertEqual(exc_info.value.code, "plan_limit_exceeded")
        details = exc_info.value.details
        self.assertEqual(details["limit_key"], "max_ml_models")
        self.assertEqual(details["max"], 0)

    def test_ml_key_routed_to_ml_plan(self):
        """ML limit keys read limits from ml_plan, not base plan."""
        ml_plan = TenantPlan.objects.create(
            name=f"ML Plan {uuid.uuid4().hex[:8]}",
            slug=f"ml-plan-{uuid.uuid4().hex[:8]}",
            tier=PlanTier.PRO,
            category="ML_AI",
            is_active=True,
            limits_json={"max_ml_models": 50},
        )
        self.tenant.ml_plan = ml_plan
        self.tenant.save(update_fields=["ml_plan"])

        with transaction.atomic():
            result = self.service.check_limit(
                str(self.tenant.id), "max_ml_models", delta=1,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["max"], 50)
        self.assertEqual(result["plan_slug"], ml_plan.slug)

    # ── Batch delta ────────────────────────────────────────────────────

    def test_batch_delta_exceeds_limit(self):
        """delta > 1 correctly accounts for bulk creation in error details."""
        self.plan.limits_json["max_assets"] = 10
        self.plan.save(update_fields=["limits_json"])
        for i in range(9):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"batch-{uuid.uuid4().hex[:8]}",
                name=f"Batch {i}",
                status=AssetStatus.ACTIVE,
            )

        with transaction.atomic():
            with pytest.raises(ValidationError) as exc_info:
                self.service.check_limit(
                    str(self.tenant.id), "max_assets", delta=3,
                )
        details = exc_info.value.details
        self.assertEqual(details["limit_key"], "max_assets")
        self.assertEqual(details["max"], 10)
        self.assertEqual(details["current"], 9)
        self.assertEqual(details["requested_delta"], 3)
        self.assertEqual(details["new_usage"], 12)

    # ── Zero limit ─────────────────────────────────────────────────────

    def test_explicit_zero_limit_blocks_all(self):
        """A plan with max_assets=0 should block any creation."""
        self.plan.limits_json["max_assets"] = 0
        self.plan.save(update_fields=["limits_json"])

        with transaction.atomic():
            with pytest.raises(ValidationError) as exc_info:
                self.service.check_limit(
                    str(self.tenant.id), "max_assets", delta=1,
                )
        self.assertEqual(exc_info.value.code, "plan_limit_exceeded")
        self.assertEqual(exc_info.value.details["max"], 0)
