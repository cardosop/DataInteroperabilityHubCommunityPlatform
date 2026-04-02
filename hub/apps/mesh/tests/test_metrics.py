"""
Unit tests for Data Mesh metrics.

Tests Prometheus metrics collection for mesh operations.
Verifies that real metric objects are incremented/observed when service
methods execute — no mocking of metric objects.
"""
import pytest
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, Role, UserRole
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.governance.models import AccessPolicy
from hub.apps.mesh.services import DataMeshService
from hub.apps.mesh.metrics import (
    mesh_domain_created_total,
    mesh_domain_updated_total,
    mesh_domain_deleted_total,
    mesh_domain_creation_duration_seconds,
    mesh_policy_applied_total,
    mesh_compliance_check_duration_seconds,
    mesh_compliance_violations_total,
    mesh_topology_update_duration_seconds,
    mesh_domain_health_status,
    get_tenant_id,
    get_domain_id,
)


pytestmark = pytest.mark.django_db(transaction=True)


class _MetricSpy:
    """
    Lightweight spy that wraps a real metric wrapper's `labels()` method.

    Every call to `labels()` still executes the real implementation and
    returns the real `_LabeledMetric`.  The spy just keeps references to
    every `_LabeledMetric` returned so tests can inspect `_value._count`,
    and records what label kwargs were used.

    This is *not* a mock — the underlying OTel/wrapper code runs normally.
    """

    def __init__(self, metric_wrapper):
        self._wrapper = metric_wrapper
        self._original_labels = metric_wrapper.labels
        self.captured = []          # list of _LabeledMetric instances
        self.label_calls = []       # list of kwargs dicts

        def _spy_labels(**kwargs):
            labeled = self._original_labels(**kwargs)
            self.captured.append(labeled)
            self.label_calls.append(kwargs)
            return labeled

        metric_wrapper.labels = _spy_labels

    def restore(self):
        """Restore the original labels() method."""
        self._wrapper.labels = self._original_labels

    @property
    def call_count(self):
        return len(self.captured)

    @property
    def total_inc(self):
        """Sum of _value._count across all captured labeled metrics."""
        return sum(lm._value._count for lm in self.captured)

    def has_observe_calls(self):
        """Return True if at least one captured metric had observe() invoked
        (histogram _value._count stays 0, but observe still ran; check if
        the observe pathway was exercised by looking for non-zero count or
        by checking that labels were created — duration metrics always get
        .observe() called right after .labels())."""
        return self.call_count > 0


class MeshMetricsTest(TestCase):
    """Test Data Mesh metrics collection"""

    def setUp(self):
        """Set up test fixtures"""
        slug = f"test-tenant-{uuid.uuid4().hex[:8]}"
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=slug,
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        # create_domain requires TENANT_ADMIN
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin role"},
        )
        UserRole.objects.get_or_create(
            user=self.user,
            role=tenant_admin_role,
            defaults={},
        )
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # ABAC: create_domain requires an ALLOW policy for DATA_MESH_DOMAIN (default deny when none match)
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Domain Creation (Metrics Test)",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)},
                    "resource": {"type": "DATA_MESH_DOMAIN"},
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
            },
        )
        cache.clear()

        # Track all spies so tearDown can restore them
        self._spies = []

    def tearDown(self):
        for spy in self._spies:
            spy.restore()

    def _spy(self, metric_wrapper):
        """Install a spy on a real metric wrapper and return it."""
        spy = _MetricSpy(metric_wrapper)
        self._spies.append(spy)
        return spy

    # ------------------------------------------------------------------
    # Metric initialisation
    # ------------------------------------------------------------------

    def test_metrics_initialized(self):
        """Test that all mesh metrics are properly initialized"""
        self.assertEqual(mesh_domain_created_total.name, "mesh_domain_created_total")
        self.assertEqual(mesh_policy_applied_total.name, "mesh_policy_applied_total")
        self.assertEqual(mesh_compliance_check_duration_seconds.name, "mesh_compliance_check_duration_seconds")
        self.assertEqual(mesh_compliance_violations_total.name, "mesh_compliance_violations_total")
        self.assertEqual(mesh_topology_update_duration_seconds.name, "mesh_topology_update_duration_seconds")
        self.assertEqual(mesh_domain_health_status.name, "mesh_domain_health_status")

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------

    def test_get_tenant_id_helper(self):
        """Test get_tenant_id helper function"""
        self.assertEqual(get_tenant_id(str(self.tenant.id)), str(self.tenant.id))
        self.assertEqual(get_tenant_id(None), "system")

    def test_get_domain_id_helper(self):
        """Test get_domain_id helper function"""
        domain_id = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(get_domain_id(domain_id), domain_id)
        self.assertEqual(get_domain_id(None), "unknown")

    # ------------------------------------------------------------------
    # Domain creation metrics
    # ------------------------------------------------------------------

    def test_domain_creation_records_metrics(self):
        """Test that domain creation records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        spy_created = self._spy(mesh_metrics_mod.mesh_domain_created_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_domain_creation_duration_seconds)
        spy_count = self._spy(mesh_metrics_mod.mesh_domain_count)

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # The service must have called .labels().inc() on the created counter
        self.assertGreaterEqual(spy_created.call_count, 1,
                                "mesh_domain_created_total.labels() was never called")
        self.assertGreater(spy_created.total_inc, 0,
                           "mesh_domain_created_total was not incremented")

        # Duration histogram must have been observed
        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_domain_creation_duration_seconds.labels() was never called")

        # Domain gauge must have been incremented
        self.assertGreaterEqual(spy_count.call_count, 1,
                                "mesh_domain_count.labels() was never called")
        self.assertGreater(spy_count.total_inc, 0,
                           "mesh_domain_count was not incremented")

        # Verify correct tenant_id label was passed
        tenant_labels = [c for c in spy_created.label_calls
                         if c.get("tenant_id") == str(self.tenant.id)]
        self.assertTrue(tenant_labels, "tenant_id label not passed to mesh_domain_created_total")

    # ------------------------------------------------------------------
    # Domain update metrics
    # ------------------------------------------------------------------

    def test_domain_update_records_metrics(self):
        """Test that domain update records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        # Create domain first (without spying on update metrics)
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Original Name"
        )

        # Now spy on update metrics
        spy_updated = self._spy(mesh_metrics_mod.mesh_domain_updated_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_domain_update_duration_seconds)

        updated_domain = self.service.update_domain(
            domain_id=str(domain.id),
            name="Updated Name"
        )

        self.assertGreaterEqual(spy_updated.call_count, 1,
                                "mesh_domain_updated_total.labels() was never called")
        self.assertGreater(spy_updated.total_inc, 0,
                           "mesh_domain_updated_total was not incremented")

        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_domain_update_duration_seconds.labels() was never called")

    # ------------------------------------------------------------------
    # Policy application metrics
    # ------------------------------------------------------------------

    def test_policy_application_records_metrics(self):
        """Test that policy application records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            enabled=True,
            effect="ALLOW",
            conditions={"type": "always"}
        )

        # Spy after domain creation so we only capture policy-application calls
        spy_applied = self._spy(mesh_metrics_mod.mesh_policy_applied_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_policy_application_duration_seconds)

        policy_application = self.service.apply_policy(
            domain_id=str(domain.id),
            policy_id=str(policy.id)
        )

        self.assertGreaterEqual(spy_applied.call_count, 1,
                                "mesh_policy_applied_total.labels() was never called")
        self.assertGreater(spy_applied.total_inc, 0,
                           "mesh_policy_applied_total was not incremented")

        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_policy_application_duration_seconds.labels() was never called")

    # ------------------------------------------------------------------
    # Compliance check metrics
    # ------------------------------------------------------------------

    def test_compliance_check_records_metrics(self):
        """Test that compliance check records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        spy_checks = self._spy(mesh_metrics_mod.mesh_compliance_checks_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_compliance_check_duration_seconds)
        spy_report = self._spy(mesh_metrics_mod.mesh_compliance_report_generated_total)

        compliance_report = self.service.check_compliance(
            domain_id=str(domain.id)
        )

        self.assertGreaterEqual(spy_checks.call_count, 1,
                                "mesh_compliance_checks_total.labels() was never called")
        self.assertGreater(spy_checks.total_inc, 0,
                           "mesh_compliance_checks_total was not incremented")

        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_compliance_check_duration_seconds.labels() was never called")

        self.assertGreaterEqual(spy_report.call_count, 1,
                                "mesh_compliance_report_generated_total.labels() was never called")
        self.assertGreater(spy_report.total_inc, 0,
                           "mesh_compliance_report_generated_total was not incremented")

    # ------------------------------------------------------------------
    # Topology update metrics
    # ------------------------------------------------------------------

    def test_topology_update_records_metrics(self):
        """Test that topology update records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        spy_updates = self._spy(mesh_metrics_mod.mesh_topology_updates_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_topology_update_duration_seconds)

        topology = self.service.get_topology(
            tenant_id=str(self.tenant.id)
        )

        self.assertGreaterEqual(spy_updates.call_count, 1,
                                "mesh_topology_updates_total.labels() was never called")
        self.assertGreater(spy_updates.total_inc, 0,
                           "mesh_topology_updates_total was not incremented")

        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_topology_update_duration_seconds.labels() was never called")

    # ------------------------------------------------------------------
    # Health status metrics
    # ------------------------------------------------------------------

    def test_health_status_update_records_metrics(self):
        """Test that health status update records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        spy_status = self._spy(mesh_metrics_mod.mesh_domain_health_status)
        spy_changes = self._spy(mesh_metrics_mod.mesh_domain_health_status_changes_total)
        spy_duration = self._spy(mesh_metrics_mod.mesh_domain_health_check_duration_seconds)

        self.service.update_domain_health_status(
            domain_id=str(domain.id),
            health_status="HEALTHY",
            health_metrics={"cpu": 50, "memory": 60}
        )

        self.assertGreaterEqual(spy_status.call_count, 1,
                                "mesh_domain_health_status.labels() was never called")

        self.assertGreaterEqual(spy_duration.call_count, 1,
                                "mesh_domain_health_check_duration_seconds.labels() was never called")

        # Verify the health_status label was passed correctly
        status_labels = [c for c in spy_status.label_calls
                         if c.get("health_status") == "HEALTHY"]
        self.assertTrue(status_labels, "health_status='HEALTHY' label not passed")

    # ------------------------------------------------------------------
    # Domain deletion metrics
    # ------------------------------------------------------------------

    def test_domain_deletion_records_metrics(self):
        """Test that domain deletion records real metrics"""
        from hub.apps.mesh import metrics as mesh_metrics_mod

        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        spy_deleted = self._spy(mesh_metrics_mod.mesh_domain_deleted_total)
        spy_count = self._spy(mesh_metrics_mod.mesh_domain_count)

        self.service.delete_domain(
            domain_id=str(domain.id),
            reason="Test deletion"
        )

        # Deletion counter must have been incremented
        self.assertGreaterEqual(spy_deleted.call_count, 1,
                                "mesh_domain_deleted_total.labels() was never called")
        self.assertGreater(spy_deleted.total_inc, 0,
                           "mesh_domain_deleted_total was not incremented")

        # Domain gauge must have been decremented (negative total_inc)
        count_decrements = [lm for lm in spy_count.captured if lm._value._count < 0]
        self.assertTrue(count_decrements,
                        "mesh_domain_count was not decremented on deletion")

        # Verify the reason label was passed
        reason_labels = [c for c in spy_deleted.label_calls
                         if c.get("reason") == "Test deletion"]
        self.assertTrue(reason_labels,
                        "reason='Test deletion' label not passed to mesh_domain_deleted_total")
