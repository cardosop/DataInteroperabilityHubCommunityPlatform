"""
Unit tests for Dataset model.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DatasetModelTest(TestCase):
    """Test Dataset model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user
        )
    
    def test_create_dataset(self):
        """Test dataset creation"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=100,
        )
        
        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.asset, self.asset)
        self.assertEqual(dataset.file, self.file)
        self.assertEqual(dataset.version, 1)
        self.assertEqual(dataset.format, "CSV")
        self.assertEqual(dataset.row_count, 100)

