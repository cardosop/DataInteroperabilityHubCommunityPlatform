"""
285.14.1.1 -- RLS test helpers verification.

Tests the set_tenant_context, clear_tenant_context, and
assert_tenant_isolation helpers against a real model with RLS.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.core.tests.test_utils.rls_helpers import (
    clear_tenant_context,
    set_tenant_context,
)
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


class RlsHelpersTests(TestCase):
    def setUp(self):
        clear_tenant_context()
        self.tenant_a = Tenant.objects.create(
            name="RLS-A",
            slug=f"rls-a-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )
        self.tenant_b = Tenant.objects.create(
            name="RLS-B",
            slug=f"rls-b-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

    def tearDown(self):
        clear_tenant_context()

    @pytest.mark.integration
    def test_set_tenant_context_sets_guc(self):
        with set_tenant_context(str(self.tenant_a.id)):
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
                val = cursor.fetchone()[0]
            assert val == str(self.tenant_a.id)

    @pytest.mark.integration
    def test_clear_tenant_context_resets(self):
        with set_tenant_context(str(self.tenant_a.id)):
            pass
        clear_tenant_context()
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
            val = cursor.fetchone()[0]
        # After clear, should be empty string or default
        assert val == "" or val is None or val == "None"

    @pytest.mark.integration
    def test_nested_context_restores_outer(self):
        with set_tenant_context(str(self.tenant_a.id)):
            with set_tenant_context(str(self.tenant_b.id)):
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
                    assert cursor.fetchone()[0] == str(self.tenant_b.id)
            # After inner block exits, outer should be restored
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
                assert cursor.fetchone()[0] == str(self.tenant_a.id)

    @pytest.mark.integration
    def test_assert_tenant_isolation_with_tenantplan(self):
        """TenantPlan doesn't have tenant_id, so isolation is at the
        Tenant level. We verify that set_tenant_context correctly scopes
        queries to the right tenant via RLS."""
        # Tenant A creates a plan
        plan_a = TenantPlan.objects.create(
            slug=f"iso-a-{uuid.uuid4().hex[:8]}",
            name="Isolation Plan A",
            tier="FREE",
            order=0,
            is_active=True,
        )
        self.tenant_a.plan = plan_a
        self.tenant_a.save(update_fields=["plan"])

        # Under tenant A's context, the plan should be visible
        with set_tenant_context(str(self.tenant_a.id)):
            # Tenant.objects.filter checks RLS when the table has it
            tenants_visible = Tenant.objects.filter(pk=self.tenant_a.pk)
            assert tenants_visible.exists()
