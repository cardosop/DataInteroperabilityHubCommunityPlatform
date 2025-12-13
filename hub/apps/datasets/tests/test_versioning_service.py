"""
Unit tests for VersioningService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch

from hub.apps.datasets.versioning_service import VersioningService
from hub.apps.datasets.models import Dataset
from hub.apps.core.services.base import NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset, AssetStatus


pytestmark = pytest.mark.django_db(transaction=True)


class VersioningServiceTest(TestCase):
    """Test VersioningService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = VersioningService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create file and asset
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
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )
        
        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            version=1
        )
    
    def test_create_version_success(self):
        """Test successful version creation"""
        new_version = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True
        )
        
        new_version.refresh_from_db()
        self.assertEqual(new_version.semantic_version, "1.1.0")
        self.assertTrue(new_version.is_current)
    
    def test_compare_versions_success(self):
        """Test successful version comparison"""
        # Create second dataset version
        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "new_field"}]},
            version=2
        )
        
        # Use real VersionComparator implementation
        result = self.service.compare_versions(
            dataset_id_1=str(self.dataset.id),
            dataset_id_2=str(dataset2.id),
            tenant_id=str(self.tenant.id)
        )
        
        # Should return comparison results
        self.assertIsInstance(result, dict)
    
    def test_get_version_history_success(self):
        """Test successful version history retrieval"""
        history = self.service.get_version_history(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIsInstance(history, list)

