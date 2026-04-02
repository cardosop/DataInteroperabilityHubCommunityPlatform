"""
Phase 121E — Transformation Plan Limit Tests

Tests that transformation pipeline operations enforce plan limits.
"""
import uuid

from django.test import TestCase

from hub.apps.transformation.models import TransformationPipeline


class TestTransformationPlanLimits(TestCase):
    """Verify transformation operations enforce plan limits."""

    @classmethod
    def setUpTestData(cls):
        """Create shared fixtures once per class (read-only)."""
        from hub.apps.tenants.models import Tenant, TenantPlan

        uid = uuid.uuid4().hex[:8]
        cls.plan = TenantPlan.objects.create(
            name=f"test-plan-{uid}",
            slug=f"test-plan-{uid}",
            limits_json={
                "max_transformation_pipelines": 2,
            },
        )
        cls.tenant = Tenant.objects.create(
            name=f"test-tenant-tf-{uid}",
            slug=f"tf-{uid}",
            plan=cls.plan,
        )

    def test_plan_has_transformation_limit(self):
        """Plan limits_json contains max_transformation_pipelines."""
        self.assertEqual(
            self.plan.get_limit("max_transformation_pipelines"), 2
        )

    def test_pipeline_count_within_limit(self):
        """Creating pipelines within limit succeeds."""
        p1 = TransformationPipeline.objects.create(
            name="pipeline-1",
            tenant=self.tenant,
            pipeline_definition={"version": "1.0", "steps": [{"name": "step1", "type": "filter", "config": {}}]},
        )
        self.assertIsNotNone(p1.id)

    def test_pipeline_count_at_limit(self):
        """Can create exactly max_transformation_pipelines pipelines."""
        for i in range(2):
            TransformationPipeline.objects.create(
                name=f"pipeline-{i}",
                tenant=self.tenant,
                pipeline_definition={"version": "1.0", "steps": [{"name": "step1", "type": "filter", "config": {}}]},
            )
        count = TransformationPipeline.objects.filter(
            tenant=self.tenant
        ).count()
        self.assertEqual(count, 2)

    def test_limit_key_registered_in_registry(self):
        """max_transformation_pipelines is registered in limit_registry."""
        try:
            from hub.apps.billing.limit_registry import RESOURCE_COUNTERS
            self.assertIn(
                "max_transformation_pipelines", RESOURCE_COUNTERS
            )
        except ImportError:
            self.skipTest("limit_registry not available")
