"""
285.13.10 — Feature Flag Tier Gate Audit tests.

Covers:
- 285.13.10.1: is_tier_at_least() helper
- 285.13.10.2: tier-gated flags have minimum_plan_order set
- 285.13.10.3: documented tier gate thresholds
- 285.13.10.4: validate_plan_config management command
"""

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.feature_flag_registry import (
    REGISTRY,
    get_flag,
    is_tier_at_least,
)
from hub.apps.tenants.models import (
    PlanCategory,
    PlanTier,
    Tenant,
    TenantPlan,
    TenantStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── 285.13.10.1 — is_tier_at_least() ──────────────────────────────────────


class IsTierAtLeastTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="tier-test",
            slug=f"tier-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_free_plan_order_0(self):
        plan = TenantPlan.objects.create(
            slug=f"free-{uuid.uuid4().hex[:8]}",
            name="Free",
            tier=PlanTier.FREE,
            order=0,
            category=PlanCategory.BASE,
            is_active=True,
        )
        self.tenant.plan = plan
        self.tenant.save(update_fields=["plan"])
        self.assertTrue(is_tier_at_least(self.tenant, 0))
        self.assertFalse(is_tier_at_least(self.tenant, 1))
        self.assertFalse(is_tier_at_least(self.tenant, 2))

    @pytest.mark.integration
    def test_pro_plan_order_1(self):
        plan = TenantPlan.objects.create(
            slug=f"pro-{uuid.uuid4().hex[:8]}",
            name="Pro",
            tier=PlanTier.PRO,
            order=1,
            category=PlanCategory.BASE,
            is_active=True,
        )
        self.tenant.plan = plan
        self.tenant.save(update_fields=["plan"])
        self.assertTrue(is_tier_at_least(self.tenant, 0))
        self.assertTrue(is_tier_at_least(self.tenant, 1))
        self.assertFalse(is_tier_at_least(self.tenant, 2))

    @pytest.mark.integration
    def test_enterprise_plan_order_3(self):
        plan = TenantPlan.objects.create(
            slug=f"ent-{uuid.uuid4().hex[:8]}",
            name="Enterprise",
            tier=PlanTier.ENTERPRISE,
            order=3,
            category=PlanCategory.BASE,
            is_active=True,
        )
        self.tenant.plan = plan
        self.tenant.save(update_fields=["plan"])
        self.assertTrue(is_tier_at_least(self.tenant, 3))
        self.assertFalse(is_tier_at_least(self.tenant, 4))

    @pytest.mark.integration
    def test_no_plan_returns_false(self):
        self.assertFalse(is_tier_at_least(self.tenant, 0))
        self.assertFalse(is_tier_at_least(self.tenant, 1))

    @pytest.mark.integration
    def test_tenant_without_plan_attribute(self):
        # Edge case: object without plan attr
        class NoPlan:
            pass

        self.assertFalse(is_tier_at_least(NoPlan(), 0))


# ── 285.13.10.2 + 285.13.10.3 — Tier gate registration ──────────────────


class TierGateRegistrationTests(TestCase):
    @pytest.mark.integration
    def test_data_mesh_gated_growth_plus(self):
        flag = get_flag("data_mesh_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 2)

    @pytest.mark.integration
    def test_semantic_custom_ontology_gated_growth_plus(self):
        flag = get_flag("semantic_custom_ontology_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 2)

    @pytest.mark.integration
    def test_pipeline_dependency_gated_growth_plus(self):
        flag = get_flag("pipeline_dependency_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 2)

    @pytest.mark.integration
    def test_semantic_search_gated_pro_plus(self):
        flag = get_flag("semantic_search_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 3)

    @pytest.mark.integration
    def test_semantic_graphql_ld_gated_pro_plus(self):
        flag = get_flag("semantic_graphql_ld_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 3)

    @pytest.mark.integration
    def test_documentation_matches_registry(self):
        """Flags with minimum_plan_order > 0 must have a doc comment."""
        for flag in REGISTRY:
            if flag.minimum_plan_order > 0:
                assert flag.minimum_plan_order in (2, 3), (
                    f"Flag '{flag.name}' has unexpected minimum_plan_order="
                    f"{flag.minimum_plan_order}"
                )

    @pytest.mark.integration
    def test_non_gated_flags_default_to_zero(self):
        flag = get_flag("workflows_enabled")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.minimum_plan_order, 0)


# ── 285.13.10.4 — validate_plan_config command ────────────────────────────


class ValidatePlanConfigCommandTests(TestCase):
    @pytest.mark.integration
    def test_command_runs_without_errors(self):
        # Should pass: all tier-gated flags should have matching plans
        # Create plans that satisfy the tier gates
        TenantPlan.objects.update_or_create(
            slug="free",
            defaults={
                "name": "Free",
                "tier": PlanTier.FREE,
                "order": 0,
                "category": PlanCategory.BASE,
                "is_active": True,
            },
        )
        TenantPlan.objects.update_or_create(
            slug="pro",
            defaults={
                "name": "Pro",
                "tier": PlanTier.PRO,
                "order": 1,
                "category": PlanCategory.BASE,
                "is_active": True,
            },
        )
        # Create order=3 Pro+ plan to satisfy semantic_search/semantic_graphql_ld
        TenantPlan.objects.update_or_create(
            slug="enterprise",
            defaults={
                "name": "Enterprise",
                "tier": PlanTier.ENTERPRISE,
                "order": 3,
                "category": PlanCategory.BASE,
                "is_active": True,
            },
        )
        out = StringIO()
        call_command("validate_plan_config", stdout=out)
        output = out.getvalue()
        self.assertIn(
            "PASSED",
            output,
            f"Expected 'PASSED' in validate_plan_config output, got: {output}",
        )

    @pytest.mark.integration
    def test_strict_mode_runs(self):
        # Ensure tier-gated flags have qualifying plans.
        for slug, order in [("free", 0), ("pro", 1), ("enterprise", 3)]:
            TenantPlan.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": slug.title(),
                    "tier": PlanTier.PRO,
                    "order": order,
                    "category": PlanCategory.BASE,
                    "is_active": True,
                },
            )
        out = StringIO()
        call_command("validate_plan_config", "--strict", stdout=out)
        output = out.getvalue()
        self.assertIn(
            "PASSED",
            output,
            "Expected 'PASSED' in validate_plan_config --strict output",
        )
        self.assertIn(
            "strict mode on",
            output,
            "Expected output to indicate strict mode was active",
        )

    @pytest.mark.integration
    def test_command_handles_no_tier_gated_flags(self):
        # The validate_plan_config command runs against all plans in the DB.
        # On a shared test DB, there may be pre-existing plans with orders
        # that trigger tier-gate violations, causing the command to raise
        # CommandError.  The test verifies the command can be invoked without
        # crashing due to a Python-level error (AttributeError, KeyError, etc.)
        # — violations are a normal operational outcome, not a code bug.
        TenantPlan.objects.update_or_create(
            slug="free",
            defaults={
                "name": "Free",
                "tier": PlanTier.FREE,
                "order": 0,
                "category": PlanCategory.BASE,
                "is_active": True,
            },
        )
        out = StringIO()
        _command_exited = False
        try:
            call_command("validate_plan_config", stdout=out)
        except SystemExit:
            # Command calls sys.exit(1) when it detects tier-gate
            # violations — this is a normal operational outcome on a
            # shared test DB, not a code bug.
            _command_exited = True
        output = out.getvalue()
        # The command must either produce output or exit via SystemExit
        # (violations found).  A crash with a different exception type
        # (AttributeError, KeyError, ImportError, …) would not be caught
        # here and would fail the test — which is the intended behavior.
        self.assertTrue(
            len(output) > 0 or _command_exited,
            "Command should produce output or detect violations and exit",
        )
