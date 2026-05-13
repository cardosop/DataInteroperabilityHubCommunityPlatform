"""
Phase 277.B.051 — Asset operations counter metrics tests.

Validates that ``asset_operations_total`` increments correctly for
each CRUD + lifecycle action with the correct labels.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.observability.metrics import asset_operations_total
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetOperationsCounterTests(TestCase):
    """Test that asset_operations_total increments with correct labels."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Metrics Tenant", slug="metrics-tenant", status=TenantStatus.ACTIVE,
        )
        self.tenant_id = str(self.tenant.id)
        self.user = User.objects.create_user(
            email="metrics@test.com", password="testpass",
        )

    # ── Counter structure ─────────────────────────────────────────

    def test_counter_exists_with_expected_labels(self):
        """Verify the counter is defined with the correct label keys."""
        self.assertEqual(asset_operations_total.name, "asset_operations_total")
        self.assertEqual(
            set(asset_operations_total._expected_labels),
            {"operation", "tenant_id", "status"},
        )

    def test_counter_increments_with_labels(self):
        """Verify inc() with attributes increases the counter."""
        labeled = asset_operations_total.labels(
            operation="create", tenant_id=self.tenant_id, status="success"
        )
        before = labeled._value.get()
        labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after - before, 1)

    # ── Label values cover all operations ─────────────────────────

    def test_all_operation_labels(self):
        """Every operation label increments independently."""
        for op in ("create", "update", "delete", "activate", "retire"):
            labeled = asset_operations_total.labels(
                operation=op, tenant_id=self.tenant_id, status="success"
            )
            before = labeled._value.get()
            labeled.inc()
            after = labeled._value.get()
            self.assertEqual(after - before, 1, f"Counter did not increment for operation={op}")

    def test_all_status_labels(self):
        """Every status label increments independently."""
        for st in ("success", "validation_error", "permission_denied", "conflict"):
            labeled = asset_operations_total.labels(
                operation="create", tenant_id=self.tenant_id, status=st
            )
            before = labeled._value.get()
            labeled.inc()
            after = labeled._value.get()
            self.assertEqual(after - before, 1, f"Counter did not increment for status={st}")

    # ── Tenant isolation ──────────────────────────────────────────

    def test_tenant_id_isolation(self):
        """Different tenant IDs produce independent counter values."""
        t2 = Tenant.objects.create(
            name="Metrics Tenant 2", slug="metrics-tenant-2", status=TenantStatus.ACTIVE,
        )
        t1_before = asset_operations_total.labels(
            operation="create", tenant_id=self.tenant_id, status="success"
        )._value.get()
        t2_before = asset_operations_total.labels(
            operation="create", tenant_id=str(t2.id), status="success"
        )._value.get()

        asset_operations_total.labels(
            operation="create", tenant_id=self.tenant_id, status="success"
        ).inc()

        t1_after = asset_operations_total.labels(
            operation="create", tenant_id=self.tenant_id, status="success"
        )._value.get()
        t2_after = asset_operations_total.labels(
            operation="create", tenant_id=str(t2.id), status="success"
        )._value.get()

        self.assertEqual(t1_after - t1_before, 1)
        self.assertEqual(t2_after - t2_before, 0)

    # ── Multiple increments ───────────────────────────────────────

    def test_multiple_increments_accumulate(self):
        """Multiple inc() calls on the same label set accumulate."""
        labeled = asset_operations_total.labels(
            operation="create", tenant_id=self.tenant_id, status="success"
        )
        before = labeled._value.get()
        for _ in range(5):
            labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after - before, 5)

    # ── Helper function emits counter ─────────────────────────────

    def test_emit_asset_operation_helper(self):
        """The _emit_asset_operation helper increments the counter."""
        from hub.apps.assets.views import _emit_asset_operation

        labeled = asset_operations_total.labels(
            operation="update", tenant_id=self.tenant_id, status="success"
        )
        before = labeled._value.get()
        _emit_asset_operation("update", self.tenant_id, "success")
        after = labeled._value.get()
        self.assertEqual(after - before, 1)

    def test_emit_asset_operation_survives_otel_failure(self):
        """Helper should not raise even if OTel is uninitialised."""
        from hub.apps.assets.views import _emit_asset_operation

        # Should never raise
        _emit_asset_operation("create", "nonexistent-tenant", "success")
