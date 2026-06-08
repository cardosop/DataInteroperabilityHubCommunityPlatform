"""
Transformation Views Tests

Comprehensive tests for transformation pipeline management endpoints.
"""
import uuid
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.db import transaction

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.users.models import UserStatus, Role
from hub.apps.auth.models import APIKey

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.uc("UC-TRANS-001"),
    pytest.mark.uc("UC-TRANS-002"),
    pytest.mark.uc("UC-TRANS-003"),
    pytest.mark.uc("UC-TRANS-004"),
    pytest.mark.uc("UC-TRANS-005"),
    pytest.mark.uc("UC-TRANS-006"),
    pytest.mark.uc("UC-TRANS-007"),
    pytest.mark.uc("UC-TRANS-008"),
]


class TransformationPipelineViewSetTest(TestCase):
    """Test suite for TransformationPipelineViewSet"""

    def setUp(self):
        """Set up per-test fixtures."""
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            transformation_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)

        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            scopes=["transformation:write", "transformation:read"]
        )

        self.client = APIClient()
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

    def test_create_pipeline_success(self):
        """Test successful pipeline creation"""
        data = {
            "name": "Test Pipeline",
            "description": "Test pipeline description",
            "pipeline_definition": self.sample_pipeline_definition,
            "version": "1.0.0",
            "status": PipelineStatus.DRAFT,
            "metadata": {"tags": ["test", "pipeline"]}
        }

        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Test Pipeline")
        self.assertEqual(response.data['status'], PipelineStatus.DRAFT)
        self.assertIn('id', response.data)
        self.assertIn('created_at', response.data)
        self.assertIn('updated_at', response.data)

        # Verify pipeline was created in database
        pipeline = TransformationPipeline.objects.get(id=response.data['id'])
        self.assertEqual(pipeline.name, "Test Pipeline")
        self.assertEqual(pipeline.tenant, self.tenant)
        self.assertEqual(pipeline.created_by, self.user)

    def test_create_pipeline_missing_required_fields(self):
        """Test pipeline creation with missing required fields"""
        data = {
            "name": "Test Pipeline",
            # Missing pipeline_definition
        }

        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_pipeline_invalid_definition(self):
        """Test pipeline creation with invalid pipeline definition"""
        data = {
            "name": "Test Pipeline",
            "pipeline_definition": {
                "version": "1.0.0",
                # Missing steps
            }
        }

        response = self.client.post(
            '/api/v1/transformation/pipelines/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pipeline_definition', str(response.data))

    def test_list_pipelines_success(self):
        """Test successful pipeline listing"""
        # Create test pipelines
        pipeline1 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Pipeline 1",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )
        pipeline2 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Pipeline 2",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        response = self.client.get('/api/v1/transformation/pipelines/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_pipelines_with_status_filter(self):
        """Test pipeline listing with status filter"""
        # Create test pipelines with different statuses
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Draft Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Active Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'status': PipelineStatus.ACTIVE}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['status'], PipelineStatus.ACTIVE)

    def test_list_pipelines_with_pagination(self):
        """Test pipeline listing with pagination"""
        # Create multiple pipelines
        for i in range(25):
            TransformationPipeline.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"Pipeline {i}",
                pipeline_definition=self.sample_pipeline_definition,
                status=PipelineStatus.DRAFT
            )

        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'page_size': 10, 'page': 1}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data.get('next'))

    def test_retrieve_pipeline_success(self):
        """Test successful pipeline retrieval"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test description",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(pipeline.id))
        self.assertEqual(response.data['name'], "Test Pipeline")
        self.assertEqual(response.data['description'], "Test description")

    def test_retrieve_pipeline_not_found(self):
        """Test pipeline retrieval with non-existent ID"""
        import uuid
        non_existent_id = uuid.uuid4()

        response = self.client.get(
            f'/api/v1/transformation/pipelines/{non_existent_id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_pipeline_success(self):
        """Test successful pipeline update"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "status": PipelineStatus.ACTIVE
        }

        response = self.client.put(
            f'/api/v1/transformation/pipelines/{pipeline.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Updated Name")
        self.assertEqual(response.data['description'], "Updated description")
        self.assertEqual(response.data['status'], PipelineStatus.ACTIVE)

        # Verify update in database
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.name, "Updated Name")
        self.assertEqual(pipeline.status, PipelineStatus.ACTIVE)

    def test_partial_update_pipeline_success(self):
        """Test successful partial pipeline update"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        data = {
            "name": "Updated Name"
        }

        response = self.client.patch(
            f'/api/v1/transformation/pipelines/{pipeline.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Updated Name")

        # Verify other fields unchanged
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.status, PipelineStatus.DRAFT)

    def test_delete_pipeline_success(self):
        """Test successful pipeline deletion"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        pipeline_id = pipeline.id

        response = self.client.delete(
            f'/api/v1/transformation/pipelines/{pipeline_id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify pipeline was deleted
        self.assertFalse(
            TransformationPipeline.objects.filter(id=pipeline_id).exists()
        )

    def test_validate_pipeline_success(self):
        """Test successful pipeline validation"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        response = self.client.post(
            f'/api/v1/transformation/pipelines/{pipeline.id}/validate/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('errors', response.data)
        self.assertIn('warnings', response.data)
        self.assertIn('details', response.data)

    def test_unauthenticated_access_denied(self):
        """Test unauthenticated access is denied"""
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_isolation(self):
        """Test tenant isolation - users can only see their tenant's pipelines"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipeline in first tenant
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Tenant 1 Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Create pipeline in other tenant
        other_pipeline = TransformationPipeline.objects.create(
            tenant=other_tenant,
            created_by=other_user,
            name="Tenant 2 Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # User should only see their tenant's pipeline
        response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(pipeline.id))

        # User should not be able to access other tenant's pipeline
        response = self.client.get(
            f'/api/v1/transformation/pipelines/{other_pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_authorization_write_operations(self):
        """Test write operations denied when ENFORCE_JWT_SCOPES=True
        and user has no transformation:write scope."""
        from django.test import override_settings

        uid2 = uuid.uuid4().hex[:8]
        # DATA_VIEWER has NO transformation scopes
        viewer = User.objects.create_user(
            email=f"viewer-{uid2}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        viewer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_VIEWER",
            defaults={"description": "Data Viewer"},
        )
        viewer.user_roles.create(role=viewer_role)

        self.client.force_authenticate(user=viewer)

        data = {
            "name": "Test Pipeline",
            "pipeline_definition": self.sample_pipeline_definition,
        }

        with override_settings(ENFORCE_JWT_SCOPES=True):
            response = self.client.post(
                '/api/v1/transformation/pipelines/',
                data, format='json',
            )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN,
        )

    def test_authorization_read_operations(self):
        """Test read operations work for authenticated users"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        self.client.force_authenticate(user=regular_user)

        # Should be able to read
        response = self.client.get('/api/v1/transformation/pipelines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f'/api/v1/transformation/pipelines/{pipeline.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_functionality(self):
        """Test search functionality in pipeline listing"""
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Customer Data Pipeline",
            description="Pipeline for customer data",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Sales Pipeline",
            description="Pipeline for sales data",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'search': 'Customer'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('Customer', response.data['results'][0]['name'])

    def test_ordering_functionality(self):
        """Test ordering functionality in pipeline listing"""
        pipeline1 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="A Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )
        pipeline2 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="B Pipeline",
            pipeline_definition=self.sample_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Test ascending order
        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'ordering': 'name'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['name'], "A Pipeline")
        self.assertEqual(response.data['results'][1]['name'], "B Pipeline")

        # Test descending order
        response = self.client.get(
            '/api/v1/transformation/pipelines/',
            {'ordering': '-name'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['name'], "B Pipeline")
        self.assertEqual(response.data['results'][1]['name'], "A Pipeline")


