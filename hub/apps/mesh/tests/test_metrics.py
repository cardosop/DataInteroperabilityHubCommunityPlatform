"""
Unit tests for Data Mesh metrics.

Tests Prometheus metrics collection for mesh operations.
"""
import pytest
import uuid
from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock
import time

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


class MeshMetricsTest(TestCase):
    """Test Data Mesh metrics collection"""

    def setUp(self):
        """Set up test fixtures"""
        slug = f"test-tenant-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
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

    def test_metrics_initialized(self):
        """Test that all mesh metrics are properly initialized"""
        # Check that metrics exist and have correct names
        self.assertEqual(mesh_domain_created_total.name, "mesh_domain_created_total")
        self.assertEqual(mesh_policy_applied_total.name, "mesh_policy_applied_total")
        self.assertEqual(mesh_compliance_check_duration_seconds.name, "mesh_compliance_check_duration_seconds")
        self.assertEqual(mesh_compliance_violations_total.name, "mesh_compliance_violations_total")
        self.assertEqual(mesh_topology_update_duration_seconds.name, "mesh_topology_update_duration_seconds")
        self.assertEqual(mesh_domain_health_status.name, "mesh_domain_health_status")

    def test_get_tenant_id_helper(self):
        """Test get_tenant_id helper function"""
        self.assertEqual(get_tenant_id(str(self.tenant.id)), str(self.tenant.id))
        self.assertEqual(get_tenant_id(None), "system")

    def test_get_domain_id_helper(self):
        """Test get_domain_id helper function"""
        domain_id = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(get_domain_id(domain_id), domain_id)
        self.assertEqual(get_domain_id(None), "unknown")

    @patch('hub.apps.mesh.services.mesh_domain_created_total')
    @patch('hub.apps.mesh.services.mesh_domain_creation_duration_seconds')
    @patch('hub.apps.mesh.services.mesh_domain_count')
    def test_domain_creation_records_metrics(self, mock_count, mock_duration, mock_created):
        """Test that domain creation records metrics"""
        # Mock metric methods
        mock_created_labels = MagicMock()
        mock_created.labels.return_value = mock_created_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        mock_count_labels = MagicMock()
        mock_count.labels.return_value = mock_count_labels
        # Mock inc method for UpDownCounterWrapper
        mock_count_labels.inc = MagicMock()

        # Create domain
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Verify metrics were called
        mock_created.labels.assert_called()
        mock_created_labels.inc.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()
        mock_count.labels.assert_called()
        mock_count_labels.inc.assert_called_once_with(1)

    @patch('hub.apps.mesh.services.mesh_domain_updated_total')
    @patch('hub.apps.mesh.services.mesh_domain_update_duration_seconds')
    def test_domain_update_records_metrics(self, mock_duration, mock_updated):
        """Test that domain update records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Original Name"
        )

        # Mock metric methods
        mock_updated_labels = MagicMock()
        mock_updated.labels.return_value = mock_updated_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        # Update domain
        updated_domain = self.service.update_domain(
            domain_id=str(domain.id),
            name="Updated Name"
        )

        # Verify metrics were called
        mock_updated.labels.assert_called()
        mock_updated_labels.inc.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()

    @patch('hub.apps.mesh.services.mesh_policy_applied_total')
    @patch('hub.apps.mesh.services.mesh_policy_application_duration_seconds')
    def test_policy_application_records_metrics(self, mock_duration, mock_applied):
        """Test that policy application records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Create a policy
        from hub.apps.governance.models import AccessPolicy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            enabled=True,
            effect="ALLOW",
            conditions={"type": "always"}
        )

        # Mock metric methods
        mock_applied_labels = MagicMock()
        mock_applied.labels.return_value = mock_applied_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        # Apply policy
        policy_application = self.service.apply_policy(
            domain_id=str(domain.id),
            policy_id=str(policy.id)
        )

        # Verify metrics were called
        mock_applied.labels.assert_called()
        mock_applied_labels.inc.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()

    @patch('hub.apps.mesh.services.mesh_compliance_checks_total')
    @patch('hub.apps.mesh.services.mesh_compliance_check_duration_seconds')
    @patch('hub.apps.mesh.services.mesh_compliance_violations_total')
    @patch('hub.apps.mesh.services.mesh_compliance_report_generated_total')
    def test_compliance_check_records_metrics(self, mock_report, mock_violations, mock_duration, mock_checks):
        """Test that compliance check records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Mock metric methods
        mock_checks_labels = MagicMock()
        mock_checks.labels.return_value = mock_checks_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        mock_violations_labels = MagicMock()
        mock_violations.labels.return_value = mock_violations_labels

        mock_report_labels = MagicMock()
        mock_report.labels.return_value = mock_report_labels

        # Check compliance
        compliance_report = self.service.check_compliance(
            domain_id=str(domain.id)
        )

        # Verify metrics were called
        mock_checks.labels.assert_called()
        mock_checks_labels.inc.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()
        mock_report.labels.assert_called()
        mock_report_labels.inc.assert_called_once()

    @patch('hub.apps.mesh.services.mesh_topology_updates_total')
    @patch('hub.apps.mesh.services.mesh_topology_update_duration_seconds')
    @patch('hub.apps.mesh.services.mesh_domain_count')
    @patch('hub.apps.mesh.services.mesh_relationship_count')
    def test_topology_update_records_metrics(self, mock_relationship, mock_domain, mock_duration, mock_updates):
        """Test that topology update records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Mock metric methods
        mock_updates_labels = MagicMock()
        mock_updates.labels.return_value = mock_updates_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        mock_domain_labels = MagicMock()
        mock_domain.labels.return_value = mock_domain_labels

        mock_relationship_labels = MagicMock()
        mock_relationship.labels.return_value = mock_relationship_labels

        # Get topology
        topology = self.service.get_topology(
            tenant_id=str(self.tenant.id)
        )

        # Verify metrics were called
        mock_updates.labels.assert_called()
        mock_updates_labels.inc.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()

    @patch('hub.apps.mesh.services.mesh_domain_health_status')
    @patch('hub.apps.mesh.services.mesh_domain_health_status_changes_total')
    @patch('hub.apps.mesh.services.mesh_domain_health_check_duration_seconds')
    def test_health_status_update_records_metrics(self, mock_duration, mock_changes, mock_status):
        """Test that health status update records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Mock metric methods
        mock_status_labels = MagicMock()
        mock_status.labels.return_value = mock_status_labels

        mock_changes_labels = MagicMock()
        mock_changes.labels.return_value = mock_changes_labels

        mock_duration_labels = MagicMock()
        mock_duration.labels.return_value = mock_duration_labels

        # Update health status
        self.service.update_domain_health_status(
            domain_id=str(domain.id),
            health_status="HEALTHY",
            health_metrics={"cpu": 50, "memory": 60}
        )

        # Verify metrics were called
        mock_status.labels.assert_called()
        mock_status_labels.set.assert_called_once()
        mock_duration.labels.assert_called()
        mock_duration_labels.observe.assert_called()

    @patch('hub.apps.mesh.services.mesh_domain_deleted_total')
    @patch('hub.apps.mesh.services.mesh_domain_count')
    def test_domain_deletion_records_metrics(self, mock_count, mock_deleted):
        """Test that domain deletion records metrics"""
        # Create domain first
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Test Domain"
        )

        # Mock metric methods
        mock_deleted_labels = MagicMock()
        mock_deleted.labels.return_value = mock_deleted_labels

        mock_count_labels = MagicMock()
        mock_count.labels.return_value = mock_count_labels
        # Mock dec method for UpDownCounterWrapper
        mock_count_labels.dec = MagicMock()

        # Delete domain
        self.service.delete_domain(
            domain_id=str(domain.id),
            reason="Test deletion"
        )

        # Verify metrics were called
        mock_deleted.labels.assert_called()
        mock_deleted_labels.inc.assert_called_once()
        mock_count.labels.assert_called()
        mock_count_labels.dec.assert_called_once_with(1)

