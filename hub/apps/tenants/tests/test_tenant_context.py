from uuid import uuid4

import pytest
from django.db import connection
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context, with_tenant_context

pytestmark = pytest.mark.django_db(transaction=True)


def _current_tenant_guc():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
        value = cursor.fetchone()[0]
        return value or None


class TenantContextTest(TestCase):
    @pytest.mark.integration
    def test_guc_set_inside_and_restored_outside(self):
        baseline = _current_tenant_guc()

        tenant_id = str(uuid4())
        with tenant_context(tenant_id):
            self.assertEqual(_current_tenant_guc(), tenant_id)

        self.assertEqual(_current_tenant_guc(), baseline)

    @pytest.mark.integration
    def test_nested_contexts_restore_outer_value(self):
        baseline = _current_tenant_guc()
        outer_tenant_id = str(uuid4())
        inner_tenant_id = str(uuid4())

        with tenant_context(outer_tenant_id):
            self.assertEqual(_current_tenant_guc(), outer_tenant_id)
            with tenant_context(inner_tenant_id):
                self.assertEqual(_current_tenant_guc(), inner_tenant_id)
            self.assertEqual(_current_tenant_guc(), outer_tenant_id)

        self.assertEqual(_current_tenant_guc(), baseline)

    @pytest.mark.integration
    def test_exception_inside_context_still_rolls_back(self):
        baseline = _current_tenant_guc()
        tenant_id = str(uuid4())

        with pytest.raises(RuntimeError), tenant_context(tenant_id):
            self.assertEqual(_current_tenant_guc(), tenant_id)
            raise RuntimeError("boom")

        self.assertEqual(_current_tenant_guc(), baseline)

    @pytest.mark.integration
    def test_with_tenant_context_decorator_applies_and_restores(self):
        baseline = _current_tenant_guc()
        tenant_id = str(uuid4())

        @with_tenant_context(tenant_id)
        def read_current_setting():
            return _current_tenant_guc()

        self.assertEqual(_current_tenant_guc(), baseline)
        self.assertEqual(read_current_setting(), tenant_id)
        self.assertEqual(_current_tenant_guc(), baseline)

    @pytest.mark.integration
    def test_with_tenant_context_decorator_restores_on_exception(self):
        baseline = _current_tenant_guc()
        tenant_id = str(uuid4())

        @with_tenant_context(tenant_id)
        def raise_inside_decorated():
            self.assertEqual(_current_tenant_guc(), tenant_id)
            raise ValueError("decorated boom")

        with pytest.raises(ValueError):
            raise_inside_decorated()
        self.assertEqual(_current_tenant_guc(), baseline)

    @pytest.mark.integration
    def test_writes_inside_context_are_not_rolled_back(self):
        tenant_id = str(uuid4())
        slug = f"tenant-context-persist-{uuid4().hex[:8]}"

        with tenant_context(tenant_id):
            Tenant.objects.create(name="Tenant Context Persist", slug=slug)

        self.assertTrue(Tenant.objects.filter(slug=slug).exists())
