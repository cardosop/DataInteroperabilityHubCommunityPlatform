"""
Security tests for transformation SQL safety — Phase 115F.4

Tests SQL injection prevention, blocked keywords, parameterization,
and DuckDB security configuration.
"""
import pytest
from django.test import TestCase

from hub.apps.transformation.business_rules import (
    TransformationBusinessRules,
)

pytestmark = pytest.mark.django_db(transaction=True)


class SQLInjectionPreventionTest(TestCase):
    """Test that SQL injection vectors are blocked by business rules."""

    def setUp(self):
        self.rules = TransformationBusinessRules(
            tenant_id="test-tenant", user_id="test-user",
        )

    def test_drop_table_in_filter_expression(self):
        """DROP TABLE in filter_expression must be rejected."""
        result = self.rules._validate_node_config(
            node_type="filter",
            node_config={
                "filter_expression": "1=1; DROP TABLE users--",
            },
            step_name="malicious_filter",
            step_index=0,
        )
        self.assertTrue(
            any("forbidden" in e.lower() or "DROP" in e for e in result),
            f"Expected rejection of DROP TABLE, got: {result}",
        )

    def test_union_select_in_transform(self):
        """UNION SELECT in transform_expression must be rejected."""
        result = self.rules._validate_node_config(
            node_type="transform",
            node_config={
                "transform_expression": "col1 UNION SELECT * FROM secrets",
            },
            step_name="union_inject",
            step_index=0,
        )
        self.assertTrue(
            any("forbidden" in e.lower() or "UNION" in e for e in result),
            f"Expected rejection, got: {result}",
        )

    def test_comment_injection_blocked(self):
        """SQL comments (-- and /*) must be rejected."""
        result = self.rules._validate_node_config(
            node_type="filter",
            node_config={
                "filter_expression": "status = 'active' -- drop table",
            },
            step_name="comment_inject",
            step_index=0,
        )
        self.assertTrue(
            any("forbidden" in e.lower() or "--" in e for e in result),
            f"Expected comment rejection, got: {result}",
        )

    def test_safe_filter_expression_allowed(self):
        """Normal filter expressions should pass validation."""
        result = self.rules._validate_node_config(
            node_type="filter",
            node_config={
                "filter_expression": "status = 'active' AND age > 18",
            },
            step_name="safe_filter",
            step_index=0,
        )
        self.assertEqual(result, [])

    def test_safe_transform_expression_allowed(self):
        """Normal transform expressions should pass."""
        result = self.rules._validate_node_config(
            node_type="transform",
            node_config={
                "transform_expression": "UPPER(name)",
            },
            step_name="safe_transform",
            step_index=0,
        )
        self.assertEqual(result, [])

    def test_insert_blocked(self):
        """INSERT statement in expression must be rejected."""
        result = self.rules._validate_node_config(
            node_type="filter",
            node_config={
                "filter_expression": "INSERT INTO users VALUES(1)",
            },
            step_name="insert_inject",
            step_index=0,
        )
        self.assertTrue(
            any("forbidden" in e.lower() or "INSERT" in e for e in result),
            f"Expected INSERT rejection, got: {result}",
        )

    def test_update_blocked(self):
        """UPDATE statement in expression must be rejected."""
        result = self.rules._validate_node_config(
            node_type="filter",
            node_config={
                "filter_expression": "UPDATE users SET admin=true",
            },
            step_name="update_inject",
            step_index=0,
        )
        self.assertTrue(
            any("forbidden" in e.lower() or "UPDATE" in e for e in result),
            f"Expected UPDATE rejection, got: {result}",
        )


class TenantIsolationTest(TestCase):
    """Test that transformation pipelines enforce tenant isolation."""

    @classmethod
    def setUpTestData(cls):
        """Create Tenants and Users once for the whole test class (read-only)."""
        from hub.apps.tenants.models import KYCStatus, Tenant
        from django.contrib.auth import get_user_model
        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        cls.tenant_a = Tenant.objects.create(
            name=f"TA-{uid}", slug=f"ta-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        cls.tenant_b = Tenant.objects.create(
            name=f"TB-{uid}", slug=f"tb-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        cls.user_a = User.objects.create_user(
            email=f"ua-{uid}@test.com", password="pass",
            tenant=cls.tenant_a,
        )
        cls.user_b = User.objects.create_user(
            email=f"ub-{uid}@test.com", password="pass",
            tenant=cls.tenant_b,
        )

    def test_pipeline_tenant_scoped(self):
        """Pipeline created in tenant A is not visible to tenant B."""
        from hub.apps.transformation.models import (
            TransformationPipeline,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant_a,
            created_by=self.user_a,
            name="Tenant A Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "s1", "type": "filter"}],
            },
        )

        # Tenant B can't see it
        visible = TransformationPipeline.objects.filter(
            tenant=self.tenant_b,
        )
        self.assertEqual(visible.count(), 0)

        # Tenant A can see it
        visible_a = TransformationPipeline.objects.filter(
            tenant=self.tenant_a,
        )
        self.assertEqual(visible_a.count(), 1)


import uuid
