"""
E2E Tests for Transformation Pipeline Management

End-to-end tests for transformation pipeline CRUD operations.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.users.models import UserStatus, Role

from .conftest import E2ETestBase

User = get_user_model()

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class TransformationPipelineE2ETest(E2ETestBase):
    """E2E tests for transformation pipeline management"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create DATA_PROVIDER role and assign to user
        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)
        
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
    
    def test_e2e_pipeline_lifecycle(self):
        """E2E test for complete pipeline lifecycle"""
        # Step 1: Create pipeline
        create_data = {
            "name": "E2E Test Pipeline",
            "description": "E2E test description",
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
        
        # Verify creation
        self.assertIsNotNone(pipeline_id)
        self.assertEqual(create_response.data['name'], "E2E Test Pipeline")
        self.assertEqual(create_response.data['status'], PipelineStatus.DRAFT)
        
        # Step 2: List pipelines and verify it appears
        list_response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_response.data['count'], 1)
        
        # Find our pipeline in the list
        pipeline_found = False
        for pipeline in list_response.data['results']:
            if pipeline['id'] == pipeline_id:
                pipeline_found = True
                self.assertEqual(pipeline['name'], "E2E Test Pipeline")
                break
        
        self.assertTrue(pipeline_found, "Pipeline should be in the list")
        
        # Step 3: Retrieve pipeline details
        retrieve_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data['id'], pipeline_id)
        self.assertEqual(retrieve_response.data['name'], "E2E Test Pipeline")
        self.assertEqual(retrieve_response.data['description'], "E2E test description")
        
        # Step 4: Validate pipeline
        validate_response = self.client.post(
            f'/api/v1/transformation/pipelines/{pipeline_id}/validate/'
        )
        
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', validate_response.data)
        self.assertIn('errors', validate_response.data)
        self.assertIn('warnings', validate_response.data)
        
        # Step 5: Update pipeline
        update_data = {
            "name": "Updated E2E Test Pipeline",
            "description": "Updated E2E test description",
            "pipeline_definition": self.sample_pipeline_definition,
            "version": "1.0.0",
            "status": PipelineStatus.ACTIVE
        }
        
        update_response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline_id}/',
            update_data,
            format='json'
        )
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['name'], "Updated E2E Test Pipeline")
        self.assertEqual(update_response.data['status'], PipelineStatus.ACTIVE)
        
        # Step 6: Verify update persisted
        retrieve_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data['name'], "Updated E2E Test Pipeline")
        self.assertEqual(retrieve_response.data['status'], PipelineStatus.ACTIVE)
        
        # Step 7: Delete pipeline
        delete_response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Step 8: Verify deletion
        retrieve_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        
        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_e2e_multi_tenant_isolation(self):
        """E2E test for multi-tenant isolation"""
        # Create pipeline in current tenant
        pipeline_data = {
            "name": "Tenant 1 Pipeline",
            "pipeline_definition": self.sample_pipeline_definition,
            "version": "1.0.0"
        }
        
        create_response = self.client.post(
            '/api/v1/transformation/pipelines/',
            pipeline_data,
            format='json'
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        pipeline_id = create_response.data['id']
        
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other E2E Tenant",
            slug="other-e2e-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        other_user = User.objects.create_user(
            email="other-e2e@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create DATA_PROVIDER role for other user
        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        other_user.user_roles.create(role=data_provider_role)
        
        # Switch to other user
        self.client.force_authenticate(user=other_user)
        
        # Other user should not see first tenant's pipeline
        list_response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 0)
        
        # Other user should not be able to access first tenant's pipeline
        retrieve_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Other user should not be able to update first tenant's pipeline
        update_response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline_id}/',
            {"name": "Hacked Pipeline", "pipeline_definition": self.sample_pipeline_definition, "version": "1.0.0"},
            format='json'
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Other user should not be able to delete first tenant's pipeline
        delete_response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_e2e_authorization_checks(self):
        """E2E test for authorization checks"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email="regular-e2e@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Regular user should be able to read
        self.client.force_authenticate(user=regular_user)
        
        # Create pipeline with authorized user first
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            '/api/v1/transformation/pipelines/',
            {
                "name": "Authorized Pipeline",
                "pipeline_definition": self.sample_pipeline_definition,
                "version": "1.0.0"
            },
            format='json'
        )
        pipeline_id = create_response.data['id']
        
        # Switch to regular user
        self.client.force_authenticate(user=regular_user)
        
        # Regular user should be able to read
        read_response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        
        # Regular user should NOT be able to create
        create_response = self.client.post(
            '/api/v1/transformation/pipelines/',
            {
                "name": "Unauthorized Pipeline",
                "pipeline_definition": self.sample_pipeline_definition,
                "version": "1.0.0"
            },
            format='json'
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Regular user should NOT be able to update
        update_response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline_id}/',
            {
                "name": "Hacked Pipeline",
                "pipeline_definition": self.sample_pipeline_definition,
                "version": "1.0.0"
            },
            format='json'
        )
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Regular user should NOT be able to delete
        delete_response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

