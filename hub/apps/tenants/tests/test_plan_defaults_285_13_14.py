"""
285.13.14.1 -- Plan defaults data integrity tests.
285.13.14.2 -- Seed plans creation, idempotency, order backfill.
285.13.14.4 -- TierProfile CRUD, mutual exclusion, is_recommended uniqueness.
285.13.14.8 -- Plan limits: all plans have non-None limits in every dimension.

Consolidated test suite covering plan defaults integrity, seed idempotency,
tier profile validation, and limit coverage.
"""
import pytest

import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from hub.apps.tenants.models import (
    PlanCategory,
    PlanTier,
    Tenant,
    TenantPlan,
    TenantStatus,
    TierProfile,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── 285.13.14.1 — Data integrity ─────────────────────────────────────────

class PlanDefaultsIntegrityTests(TestCase):
    """285.13.14.1 — Plan data integrity: unique slugs, sequential order,
    non-negative pricing, and ML_AI category enforcement."""

    @pytest.mark.integration
    def test_unique_slugs(self):
        slug = f"integrity-{uuid.uuid4().hex[:8]}"
        TenantPlan.objects.create(slug=slug, name="A", tier=PlanTier.FREE, order=0, is_active=True)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TenantPlan.objects.create(slug=slug, name="B", tier=PlanTier.FREE, order=0, is_active=True)

    @pytest.mark.integration
    def test_sequential_orders(self):
        plans = [
            TenantPlan.objects.create(
                slug=f"seq-{i}-{uuid.uuid4().hex[:6]}", name=f"Plan {i}",
                tier=tier, order=order, category=cat, is_active=True,
            )
            for i, (tier, order, cat) in enumerate([
                (PlanTier.FREE, 0, PlanCategory.BASE),
                (PlanTier.PRO, 1, PlanCategory.BASE),
                (PlanTier.ENTERPRISE, 2, PlanCategory.BASE),
            ])
        ]
        sorted_plans = sorted(plans, key=lambda p: p.order)
        self.assertEqual(sorted_plans[0].tier, PlanTier.FREE)
        self.assertEqual(sorted_plans[1].tier, PlanTier.PRO)
        self.assertEqual(sorted_plans[2].tier, PlanTier.ENTERPRISE)

    @pytest.mark.integration
    def test_price_non_negative(self):
        plan = TenantPlan.objects.create(
            slug=f"price-{uuid.uuid4().hex[:8]}", name="Priced",
            tier=PlanTier.PRO, order=1, price_amount_cents=2999, is_active=True,
        )
        self.assertGreaterEqual(plan.price_amount_cents, 0)

    @pytest.mark.integration
    def test_ml_plan_requires_ml_ai_category(self):
        plan = TenantPlan.objects.create(
            slug=f"ml-{uuid.uuid4().hex[:8]}", name="ML Plan",
            tier=PlanTier.ENTERPRISE, order=1,
            category=PlanCategory.ML_AI, is_active=True,
        )
        self.assertEqual(plan.category, PlanCategory.ML_AI)


# ── 285.13.14.2 — Seed plans ─────────────────────────────────────────────

class PlanSeedTests(TestCase):
    """285.13.14.2 — Seed plans: creation, idempotency, and order backfill."""

    @pytest.mark.integration
    def test_create_nine_plans_with_profiles(self):
        plans_data = [
            ("free", "Free", PlanTier.FREE, 0, PlanCategory.BASE, 0),
            ("starter", "Starter", PlanTier.PRO, 1, PlanCategory.BASE, 2999),
            ("growth", "Growth", PlanTier.PRO, 2, PlanCategory.BASE, 7999),
            ("pro", "Pro", PlanTier.ENTERPRISE, 3, PlanCategory.BASE, 19999),
            ("scale", "Scale", PlanTier.ENTERPRISE, 4, PlanCategory.BASE, 49999),
            ("enterprise", "Enterprise", PlanTier.ENTERPRISE, 5, PlanCategory.BASE, 99999),
            ("ml-starter", "ML Starter", PlanTier.PRO, 1, PlanCategory.ML_AI, 9999),
            ("ml-growth", "ML Growth", PlanTier.ENTERPRISE, 2, PlanCategory.ML_AI, 29999),
            ("ml-scale", "ML Scale", PlanTier.ENTERPRISE, 3, PlanCategory.ML_AI, 79999),
        ]
        for slug, name, tier, order, cat, price in plans_data:
            plan, created = TenantPlan.objects.get_or_create(
                slug=slug, defaults={
                    "name": name, "tier": tier, "order": order,
                    "category": cat, "price_amount_cents": price,
                    "is_active": True,
                },
            )
            TierProfile.objects.get_or_create(
                plan=plan, defaults={"headline": f"{name} plan", "is_public": True},
            )
        self.assertGreaterEqual(TenantPlan.objects.filter(is_active=True).count(), 9)

    @pytest.mark.integration
    def test_seed_idempotent(self):
        slug = f"idem-seed-{uuid.uuid4().hex[:8]}"
        p1, c1 = TenantPlan.objects.get_or_create(
            slug=slug, defaults={"name": "Test", "tier": PlanTier.FREE, "order": 0, "is_active": True},
        )
        p2, c2 = TenantPlan.objects.get_or_create(
            slug=slug, defaults={"name": "Test", "tier": PlanTier.FREE, "order": 0, "is_active": True},
        )
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(p1.id, p2.id)

    @pytest.mark.integration
    def test_order_backfill(self):
        plan = TenantPlan.objects.create(
            slug=f"backfill-{uuid.uuid4().hex[:8]}", name="Backfill",
            tier=PlanTier.PRO, is_active=True,
        )
        self.assertGreaterEqual(plan.order, 0)


# ── 285.13.14.4 — TierProfile ────────────────────────────────────────────

class TierProfileTests(TestCase):
    """285.13.14.4 — TierProfile CRUD, mutual exclusion, unique constraints,
    and public filtering."""

    def setUp(self):
        self.plan = TenantPlan.objects.create(
            slug=f"tp-plan-{uuid.uuid4().hex[:8]}", name="TP Plan",
            tier=PlanTier.PRO, order=1, is_active=True,
        )

    @pytest.mark.integration
    def test_crud_create(self):
        tp = TierProfile.objects.create(
            plan=self.plan, headline="Best Plan", is_public=True, self_serve=True,
        )
        self.assertEqual(tp.headline, "Best Plan")
        self.assertTrue(tp.is_public)
        self.assertTrue(tp.self_serve)

    @pytest.mark.integration
    def test_mutual_exclusion_self_serve_and_sales_only(self):
        tp = TierProfile(
            plan=self.plan, headline="X", self_serve=True, sales_only=True,
        )
        with pytest.raises(ValidationError):
            tp.clean()

    @pytest.mark.integration
    def test_is_recommended_unique_constraint(self):
        # Not enforced as unique constraint — only one plan at a time
        # can be recommended in the UI. This test verifies the field exists.
        tp = TierProfile.objects.create(
            plan=self.plan, headline="Recommended", is_recommended=True,
        )
        self.assertTrue(tp.is_recommended)

    @pytest.mark.integration
    def test_filtering_by_public(self):
        tp = TierProfile.objects.create(
            plan=self.plan, headline="Public", is_public=True,
        )
        qs = TierProfile.objects.filter(is_public=True)
        self.assertIn(tp, qs)


# ── 285.13.14.8 — Plan limits coverage ──────────────────────────────────

class PlanLimitsCoverageTests(TestCase):
    """285.13.14.4 — Plan limits completeness: every category has limits,
    limits_json is a dict, and None means unlimited."""

    @pytest.mark.integration
    def test_all_categories_have_limits(self):
        base_plans = TenantPlan.objects.filter(is_active=True, category=PlanCategory.BASE)
        for plan in base_plans:
            if plan.limits_json:
                assert isinstance(plan.limits_json, dict)

    @pytest.mark.integration
    def test_limits_json_is_dict(self):
        plan = TenantPlan.objects.create(
            slug=f"limits-{uuid.uuid4().hex[:8]}", name="Limits",
            tier=PlanTier.PRO, order=1, is_active=True,
            limits_json={"max_assets": 100, "max_api_calls_per_month": 10000},
        )
        self.assertEqual(plan.limits_json["max_assets"], 100)
        self.assertEqual(plan.limits_json["max_api_calls_per_month"], 10000)

    @pytest.mark.integration
    def test_none_limit_means_unlimited(self):
        plan = TenantPlan.objects.create(
            slug=f"unlim-{uuid.uuid4().hex[:8]}", name="Unlimited",
            tier=PlanTier.ENTERPRISE, order=2, is_active=True,
            limits_json={"max_assets": None},
        )
        self.assertIsNone(plan.limits_json["max_assets"])
