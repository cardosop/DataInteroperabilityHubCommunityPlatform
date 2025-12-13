"""
Unit tests for DatasetService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, Mock

from hub.apps.datasets.services import DatasetService
from hub.apps.datasets.models import Dataset
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset, AssetStatus


pytestmark = pytest.mark.django_db(transaction=True)


class DatasetServiceTest(TestCase):
    """Test DatasetService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = DatasetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create file
        import uuid
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv"
        )
    
    def test_create_dataset_success(self):
        """Test successful dataset creation"""
        with patch('hub.apps.datasets.services.boto3') as mock_boto3:
            # Mock S3 client
            mock_s3_client = Mock()
            mock_boto3.client.return_value = mock_s3_client
            
            # Mock S3 response - need to properly mock the response structure
            mock_body = Mock()
            mock_body.read.return_value = b'id,name\n1,test1\n2,test2\n'
            mock_response = {'Body': mock_body}
            mock_s3_client.get_object.return_value = mock_response
            mock_s3_client.head_object.return_value = {}
            
            dataset = self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(self.file.id)
            )
            
            self.assertIsNotNone(dataset)
            self.assertEqual(dataset.file_id, self.file.id)
            self.assertIsNotNone(dataset.schema_json)
    
    def test_create_dataset_file_not_found(self):
        """Test dataset creation with non-existent file"""
        with self.assertRaises(NotFoundError):
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id="00000000-0000-0000-0000-000000000000"
            )
    
    def test_create_dataset_file_not_active(self):
        """Test dataset creation with inactive file"""
        self.file.status = FileStatus.FAILED
        self.file.save()
        
        with self.assertRaises(ValidationError) as cm:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(self.file.id)
            )
        
        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
    
    def test_get_dataset_success(self):
        """Test successful dataset retrieval"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []}
        )
        
        retrieved = self.service.get_dataset(
            dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(retrieved.id, dataset.id)

