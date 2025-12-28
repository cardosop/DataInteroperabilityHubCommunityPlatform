"""
Transformation Views Authorization Integration Tests

Integration tests for authorization checks including:
- Complete authorization flow with real services
- ABAC policy enforcement in real scenarios
- Cross-tenant access validation
- Permission enforcement across all operations
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.users.models import UserStatus, Role
from hub.apps.governance.models import AccessPolicy

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TransformationPipelineAuthorizationIntegrationTest(TestCase):
    """Integration tests for authorization in TransformationPipelineViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Authorization Integration Test Tenant",
            slug="auth-integration-test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create user with DATA_PROVIDER role
        self.data_provider_user = User.objects.create_user(
            email="dataprovider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role and assign to user
        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.data_provider_user.user_roles.create(role=data_provider_role)

        # Sample pipeline definition
        self.sample_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "filter",
                    "config": {
                        "filter_expression": "status == 'active'"
                    }
                }
            ]
        }

    def test_complete_authorization_flow(self):
        """Test complete authorization flow from creation to deletion"""
        # Authenticate as data provider user
        self.client.force_authenticate(user=self.data_provider_user)

        # Create pipeline
        data = {
            "name": "Integration Test Pipeline",
            "pipeline_definition": self.sample_pipeline_definition
        }

        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pipeline_id = response.data['id']

        # Read pipeline
        response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Update pipeline
        update_data = {
            "name": "Updated Integration Test Pipeline",
            "pipeline_definition": self.sample_pipeline_definition,
            "version": "1.0.0",
            "status": PipelineStatus.DRAFT
        }

        response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline_id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Delete pipeline
        response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_abac_policy_enforcement_integration(self):
        """Test ABAC policy enforcement in integration scenario"""
        # Create a DENY policy for transformation pipelines
        deny_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Pipeline Access Integration",
            effect="DENY",
            conditions={
                "resource_type": "TRANSFORMATION_PIPELINE",
                "user": {
                    "user_roles": ["DATA_PROVIDER"]
                }
            },
            enabled=True
        )

        # Authenticate as data provider user
        self.client.force_authenticate(user=self.data_provider_user)

        # Try to create pipeline - should be denied by ABAC policy
        data = {
            "name": "Test Pipeline",
            "pipeline_definition": self.sample_pipeline_definition
        }

        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        # Should be denied by ABAC policy (403 Forbidden)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("ABAC policy denied", str(response.data))

        # Disable the policy
        deny_policy.enabled = False
        deny_policy.save()

        # Now should be able to create
        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Clean up
        deny_policy.delete()

    def test_cross_tenant_isolation_integration(self):
        """Test cross-tenant isolation in integration scenario"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant Integration",
            slug="other-tenant-integration",
            kyc_status=KYCStatus.VERIFIED
        )

        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipeline in other tenant
        other_pipeline = TransformationPipeline.objects.create(
            tenant=other_tenant,
            created_by=other_user,
            name="Other Tenant Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Current tenant user should not be able to access other tenant's pipeline
        self.client.force_authenticate(user=self.data_provider_user)

        # Should not be able to read
        response = self.client.get(
            f'/api/v1/transformation/pipelines/{other_pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Should not be able to update
        response = self.client.put(
            f'/api/v1/transformation/pipelines/{other_pipeline.id}/',
            {
                "name": "Updated",
                "pipeline_definition": self.sample_pipeline_definition,
                "version": "1.0.0",
                "status": PipelineStatus.DRAFT
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Should not be able to delete
        response = self.client.delete(
            f'/api/v1/transformation/pipelines/{other_pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_permission_enforcement_across_operations(self):
        """Test permission enforcement across all CRUD operations"""
        # Create a pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Permission Test Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Create a regular user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email="regular@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Regular user should be able to read
        self.client.force_authenticate(user=regular_user)

        response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user should NOT be able to update (no DATA_PROVIDER role)
        response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline.id}/',
            {
                "name": "Updated",
                "pipeline_definition": self.sample_pipeline_definition,
                "version": "1.0.0",
                "status": PipelineStatus.DRAFT
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Regular user should NOT be able to delete (no DATA_PROVIDER role)
        response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Regular user should NOT be able to create (no DATA_PROVIDER role)
        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            {
                "name": "New Pipeline",
                "pipeline_definition": self.sample_pipeline_definition
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

