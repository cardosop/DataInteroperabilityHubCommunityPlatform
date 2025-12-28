"""
Transformation Views Integration Tests

Integration tests for transformation pipeline management API.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.users.models import UserStatus, Role
from hub.apps.auth.models import APIKey

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TransformationPipelineIntegrationTest(TestCase):
    """Integration tests for transformation pipeline API"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Integration Test Tenant",
            slug="integration-test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email="integration@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role and assign to user
        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)

        # Authenticate client
        self.client.force_authenticate(user=self.user)

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
                },
                {
                    "name": "transform_step",
                    "type": "transform",
                    "config": {
                        "transform_expression": "upper(name)"
                    }
                }
            ]
        }

    def test_full_crud_workflow(self):
        """Test complete CRUD workflow for pipelines"""
        # Create
        create_data = {
            "name": "Integration Test Pipeline",
            "description": "Integration test description",
            "pipeline_definition": self.sample_pipeline_definition,
            "version": "1.0.0",
            "status": PipelineStatus.DRAFT
        }

        create_response = self.client.post(
            '/api/v1/transformation/pipelines/',
            create_data,
            format='json'
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        pipeline_id = create_response.data['id']

        # Read
        read_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['name'], "Integration Test Pipeline")

        # Update
        update_data = {
            "name": "Updated Integration Test Pipeline",
            "status": PipelineStatus.ACTIVE
        }

        update_response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline_id}/',
            {**create_data, **update_data},
            format='json'
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['name'], "Updated Integration Test Pipeline")
        self.assertEqual(update_response.data['status'], PipelineStatus.ACTIVE)

        # Validate
        validate_response = self.client.post(
            f'/api/v1/transformation/pipelines/{pipeline_id}/validate/'
        )

        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', validate_response.data)

        # Delete
        delete_response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        verify_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(verify_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_with_filters_and_pagination(self):
        """Test listing with filters and pagination"""
        # Create multiple pipelines with different statuses
        for i in range(15):
            TransformationPipeline.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"Pipeline {i}",
                pipeline_definition=self.sample_pipeline_definition,
                status=PipelineStatus.DRAFT if i % 2 == 0 else PipelineStatus.ACTIVE
            )

        # Test status filter
        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'status': PipelineStatus.ACTIVE}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)
        for result in response.data['results']:
            self.assertEqual(result['status'], PipelineStatus.ACTIVE)

        # Test pagination
        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'page_size': 5, 'page': 1}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 15)
        self.assertEqual(len(response.data['results']), 5)

    def test_tenant_isolation_integration(self):
        """Test tenant isolation in integration scenario"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Integration Tenant",
            slug="other-integration-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipelines in both tenants
        pipeline1 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Tenant 1 Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        pipeline2 = TransformationPipeline.objects.create(
            tenant=other_tenant,
            created_by=other_user,
            name="Tenant 2 Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Current user should only see their tenant's pipeline
        response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(pipeline1.id))

        # Switch to other user
        self.client.force_authenticate(user=other_user)

        # Other user should only see their tenant's pipeline
        response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(pipeline2.id))

    def test_validation_integration(self):
        """Test pipeline validation integration"""
        # Create valid pipeline
        valid_pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Valid Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        response = self.client.post(
            f'/api/v1/transformation/pipelines/{valid_pipeline.id}/validate/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('errors', response.data)
        self.assertIn('warnings', response.data)

        # Create invalid pipeline (missing required fields)
        # We need to bypass model validation to create an invalid pipeline for testing
        # First create a valid pipeline, then update it to be invalid using update()
        # which bypasses model validation
        invalid_pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Invalid Pipeline",
            pipeline_definition=self.sample_pipeline_definition,  # Start with valid definition
            status=PipelineStatus.DRAFT
        )

        # Now update it to be invalid using update() which bypasses validation
        invalid_pipeline_definition = {
            "version": "1.0.0",
            # Missing steps
        }
        TransformationPipeline.objects.filter(id=invalid_pipeline.id).update(
            pipeline_definition=invalid_pipeline_definition
        )
        invalid_pipeline.refresh_from_db()

        response = self.client.post(
            f'/api/v1/transformation/pipelines/{invalid_pipeline.id}/validate/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Validation should return is_valid=False with errors
        self.assertFalse(response.data['is_valid'])
        self.assertGreater(len(response.data['errors']), 0)


