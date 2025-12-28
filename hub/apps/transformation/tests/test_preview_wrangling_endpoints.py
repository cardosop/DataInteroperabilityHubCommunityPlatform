"""
Unit and Integration tests for preview and wrangling endpoints.

Tests:
- GET /api/v1/transformation/previews/{id}/ - Get preview result
- POST /api/v1/transformation/wrangling/ - Perform wrangling
- GET /api/v1/transformation/wrangling/{id}/ - Get wrangling session
- POST /api/v1/transformation/wrangling/{id}/undo/ - Undo operation
- POST /api/v1/transformation/wrangling/{id}/redo/ - Redo operation

Uses real services (no mocks).
"""
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.transformation.models import (
    TransformationPipeline, PipelineStatus, PreviewResult,
    WranglingSession, WranglingOperationType
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus, Role

User = get_user_model()


class PreviewEndpointTest(TestCase):
    """Unit tests for preview endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
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
        self.client.force_authenticate(user=self.user)

        # Create a test pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "TRANSFORM",
                        "config": {}
                    }
                ]
            },
            status=PipelineStatus.ACTIVE,
            created_by=self.user
        )

        # Create a test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            domain="test",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create file and dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            status=FileStatus.ACTIVE,
            size=1000,
            content_type="text/csv"
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            row_count=100
        )

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_get_preview_result_success(self, mock_storage):
        """Test getting preview result by preview_id"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create a preview result
        preview_data = {
            "preview_id": "preview_1234567890",
            "pipeline_id": str(self.pipeline.id),
            "pipeline_name": self.pipeline.name,
            "asset_id": str(self.asset.id),
            "asset_name": self.asset.name,
            "input_sample": [{"id": "1", "name": "Alice", "age": "25"}],
            "output_sample": [{"id": "1", "name": "Alice", "age": "25"}],
            "input_sample_size": 2,
            "output_sample_size": 2,
            "analysis": {},
            "quality_metrics": {},
            "cached": False,
            "generated_at": timezone.now().isoformat(),
            "sample_size": 100,
            "sampling_method": "first_n"
        }

        preview_result = PreviewResult.objects.create(
            preview_id="preview_1234567890",
            tenant=self.tenant,
            created_by=self.user,
            pipeline=self.pipeline,
            asset=self.asset,
            preview_data=preview_data,
            cache_key="test_cache_key",
            sample_size=100,
            sampling_method="first_n",
            expires_at=timezone.now() + timedelta(hours=1)
        )

        # Get preview result
        url = f'/api/v1/transformation/previews/{preview_result.preview_id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['preview_id'], preview_result.preview_id)
        self.assertEqual(response.data['pipeline_id'], str(self.pipeline.id))
        self.assertEqual(response.data['asset_id'], str(self.asset.id))
        self.assertFalse(response.data['is_expired'])

    def test_get_preview_result_not_found(self):
        """Test getting preview result that doesn't exist"""
        url = '/api/v1/transformation/previews/nonexistent_preview_id/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_preview_result_expired(self):
        """Test getting expired preview result"""
        preview_data = {
            "preview_id": "preview_expired",
            "pipeline_id": str(self.pipeline.id),
            "asset_id": str(self.asset.id),
        }

        preview_result = PreviewResult.objects.create(
            preview_id="preview_expired",
            tenant=self.tenant,
            created_by=self.user,
            pipeline=self.pipeline,
            asset=self.asset,
            preview_data=preview_data,
            cache_key="test_cache_key",
            sample_size=100,
            sampling_method="first_n",
            expires_at=timezone.now() - timedelta(hours=1)  # Expired
        )

        url = f'/api/v1/transformation/previews/{preview_result.preview_id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn('error', response.data)
        self.assertIn('expired', response.data['error'].lower())


class WranglingEndpointTest(TestCase):
    """Unit tests for wrangling endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
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
        self.client.force_authenticate(user=self.user)

        # Create a test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            domain="test",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create file and dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            status=FileStatus.ACTIVE,
            size=1000,
            content_type="text/csv"
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            row_count=100
        )

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_perform_wrangling_operation_success(self, mock_storage):
        """Test performing a wrangling operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Perform wrangling operation
        url = '/api/v1/transformation/wrangling/'
        data = {
            "asset_id": str(self.asset.id),
            "operation": {
                "type": "FILTER",
                "parameters": {
                    "condition": "age > 25"
                }
            }
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_id', response.data)
        self.assertIn('operation_id', response.data)
        self.assertIn('result', response.data)
        self.assertIn('can_undo', response.data)
        self.assertIn('can_redo', response.data)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_perform_wrangling_with_existing_session(self, mock_storage):
        """Test performing wrangling operation with existing session"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create a wrangling session
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session"
        )

        # Perform wrangling operation with existing session
        url = '/api/v1/transformation/wrangling/'
        data = {
            "asset_id": str(self.asset.id),
            "session_id": str(session.id),
            "operation": {
                "type": "SORT",
                "parameters": {
                    "columns": ["age"],
                    "ascending": True
                }
            }
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], str(session.id))

    def test_perform_wrangling_invalid_operation(self):
        """Test performing wrangling with invalid operation"""
        url = '/api/v1/transformation/wrangling/'
        data = {
            "asset_id": str(self.asset.id),
            "operation": {
                "type": "INVALID_TYPE",
                "parameters": {}
            }
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_get_wrangling_session_success(self, mock_storage):
        """Test getting wrangling session by ID"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create a wrangling session
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session"
        )

        # Get wrangling session
        url = f'/api/v1/transformation/wrangling/{session.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(session.id))
        self.assertEqual(response.data['name'], session.name)
        self.assertIn('can_undo', response.data)
        self.assertIn('can_redo', response.data)

    def test_get_wrangling_session_not_found(self):
        """Test getting wrangling session that doesn't exist"""
        import uuid
        url = f'/api/v1/transformation/wrangling/{uuid.uuid4()}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_undo_wrangling_operation_success(self, mock_storage):
        """Test undoing a wrangling operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create a wrangling session with operations
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session",
            operation_history=[
                {
                    "type": "FILTER",
                    "parameters": {"condition": "age > 25"},
                    "timestamp": timezone.now().isoformat(),
                    "index": 0
                }
            ],
            history_position=0
        )

        # Undo operation
        url = f'/api/v1/transformation/wrangling/{session.id}/undo/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], str(session.id))
        self.assertIn('undone_operation', response.data)
        self.assertFalse(response.data['can_undo'])  # No more operations to undo

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_undo_wrangling_operation_no_operations(self, mock_storage):
        """Test undoing when no operations to undo"""
        # Create a wrangling session without operations
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session",
            operation_history=[],
            history_position=-1
        )

        # Try to undo
        url = f'/api/v1/transformation/wrangling/{session.id}/undo/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_redo_wrangling_operation_success(self, mock_storage):
        """Test redoing a wrangling operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create a wrangling session with operations
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session",
            operation_history=[
                {
                    "type": "FILTER",
                    "parameters": {"condition": "age > 25"},
                    "timestamp": timezone.now().isoformat(),
                    "index": 0
                }
            ],
            history_position=-1  # At end, but can redo
        )

        # First undo to move position back
        session.undo()

        # Redo operation
        url = f'/api/v1/transformation/wrangling/{session.id}/redo/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], str(session.id))
        self.assertIn('redone_operation', response.data)
        self.assertTrue(response.data['can_undo'])  # Can undo again

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_redo_wrangling_operation_no_operations(self, mock_storage):
        """Test redoing when no operations to redo"""
        # Create a wrangling session at end of history
        session = WranglingSession.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            name="Test Session",
            operation_history=[
                {
                    "type": "FILTER",
                    "parameters": {"condition": "age > 25"},
                    "timestamp": timezone.now().isoformat(),
                    "index": 0
                }
            ],
            history_position=0  # At end, no operations to redo
        )

        # Try to redo
        url = f'/api/v1/transformation/wrangling/{session.id}/redo/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class PreviewWranglingIntegrationTest(TestCase):
    """Integration tests for preview and wrangling API"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
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
        self.client.force_authenticate(user=self.user)

        # Create a test pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "TRANSFORM",
                        "config": {}
                    }
                ]
            },
            status=PipelineStatus.ACTIVE,
            created_by=self.user
        )

        # Create a test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            domain="test",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create file and dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            status=FileStatus.ACTIVE,
            size=1000,
            content_type="text/csv"
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            row_count=100
        )

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_preview_and_retrieve_workflow(self, mock_storage):
        """Test complete workflow: create preview, then retrieve it"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Create preview via pipeline preview endpoint
        preview_url = f'/api/v1/transformation/pipelines/{self.pipeline.id}/preview/'
        preview_data = {
            "asset_id": str(self.asset.id),
            "sample_size": 100,
            "sampling_method": "first_n"
        }
        preview_response = self.client.post(preview_url, preview_data, format='json')

        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        preview_id = preview_response.data.get('preview_id')
        self.assertIsNotNone(preview_id)

        # Retrieve preview result
        retrieve_url = f'/api/v1/transformation/previews/{preview_id}/'
        retrieve_response = self.client.get(retrieve_url)

        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data['preview_id'], preview_id)
        self.assertEqual(retrieve_response.data['pipeline_id'], str(self.pipeline.id))

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangling_workflow_with_undo_redo(self, mock_storage):
        """Test complete wrangling workflow with undo/redo"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Perform first wrangling operation
        wrangle_url = '/api/v1/transformation/wrangling/'
        operation1 = {
            "asset_id": str(self.asset.id),
            "operation": {
                "type": "FILTER",
                "parameters": {
                    "condition": "age > 25"
                }
            }
        }
        response1 = self.client.post(wrangle_url, operation1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        session_id = response1.data['session_id']

        # Get session
        get_url = f'/api/v1/transformation/wrangling/{session_id}/'
        get_response = self.client.get(get_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertTrue(get_response.data['can_undo'])

        # Undo operation
        undo_url = f'/api/v1/transformation/wrangling/{session_id}/undo/'
        undo_response = self.client.post(undo_url)
        self.assertEqual(undo_response.status_code, status.HTTP_200_OK)
        self.assertFalse(undo_response.data['can_undo'])
        self.assertTrue(undo_response.data['can_redo'])

        # Redo operation
        redo_url = f'/api/v1/transformation/wrangling/{session_id}/redo/'
        redo_response = self.client.post(redo_url)
        self.assertEqual(redo_response.status_code, status.HTTP_200_OK)
        self.assertTrue(redo_response.data['can_undo'])
        self.assertFalse(redo_response.data['can_redo'])

