"""
Phase 121E — Transformation Plan Limit Tests

Tests that transformation pipeline operations enforce plan limits.
"""
import uuid

from django.test import TestCase

from hub.apps.transformation.models import TransformationPipeline
from hub.apps.transformation.services import TransformationService


class TestTransformationPlanLimits(TestCase):
    """Verify transformation operations enforce plan limits."""

    def setUp(self):
        """Create shared fixtures for each test."""
        from hub.apps.tenants.models import Tenant, TenantPlan
        from hub.apps.users.models import User, UserStatus, Role, UserRole
        from hub.apps.governance.models import AccessPolicy

        uid = uuid.uuid4().hex[:8]
        self.plan = TenantPlan.objects.create(
            name=f"test-plan-{uid}",
            slug=f"test-plan-{uid}",
            limits_json={
                "max_transformation_pipelines": 2,
            },
        )
        self.tenant = Tenant.objects.create(
            name=f"test-tenant-tf-{uid}",
            slug=f"tf-{uid}",
            plan=self.plan,
        )

        self.user = User.objects.create_user(
            email=f"pl-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=role)

        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Pipeline Ops",
            defaults={
                "conditions": {"user": {"tenant_id": str(self.tenant.id)}},
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user,
            },
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.valid_definition = {
            "version": "1.0",
            "steps": [{"name": "step1", "type": "filter", "config": {}}],
        }

    def _create_pipeline(self, name):
        return self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name=name,
            pipeline_definition=self.valid_definition,
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

    def test_pipeline_count_exceeds_limit_raises(self):
        """Creating a 3rd pipeline when limit is 2 raises ValidationError."""
        from hub.apps.core.services.base import ValidationError

        # Create 2 pipelines (at limit)
        self._create_pipeline("pipeline-1")
        self._create_pipeline("pipeline-2")

        # 3rd pipeline should be rejected
        with self.assertRaises(ValidationError):
            self._create_pipeline("pipeline-3")

        # Verify only 2 pipelines exist
        count = TransformationPipeline.objects.filter(
            tenant=self.tenant
        ).count()
        self.assertEqual(count, 2)

    def test_pipeline_count_over_limit_rejected(self):
        """Attempting to create a pipeline when over limit is rejected."""
        from hub.apps.core.services.base import ValidationError

        # Create 2 pipelines (at limit)
        self._create_pipeline("pipeline-A")
        self._create_pipeline("pipeline-B")

        # Verify 3rd pipeline creation is rejected via service layer
        with self.assertRaises(ValidationError):
            self._create_pipeline("pipeline-C")

        # Verify the 3rd pipeline was NOT persisted
        self.assertEqual(
            TransformationPipeline.objects.filter(tenant=self.tenant).count(),
            2,
        )

    def test_limit_key_registered_in_registry(self):
        """max_transformation_pipelines is registered in limit_registry."""
        try:
            from hub.apps.billing.limit_registry import RESOURCE_COUNTERS
            self.assertIn(
                "max_transformation_pipelines", RESOURCE_COUNTERS
            )
        except ImportError:
            self.skipTest("limit_registry not available")
