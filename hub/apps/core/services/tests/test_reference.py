"""
Unit tests for ReferenceService

Tests for cross-app reference validation and retrieval.
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.core.services.reference import ReferenceService
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.contracts.models import Contract, ContractStatus

User = get_user_model()

uid = uuid.uuid4().hex[:8]


class ReferenceServiceTest(TestCase):
    """Test ReferenceService functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="password",
            tenant=self.tenant
        )
        self.service = ReferenceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create test resources
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
    
    def test_register_model(self):
        """Test model registration."""
        from hub.apps.datasets.models import Dataset
        
        ReferenceService.register_model("datasets", "Dataset", Dataset)
        model_class = ReferenceService.get_model_class("datasets", "Dataset")
        self.assertEqual(model_class, Dataset)
    
    def test_get_model_class_not_registered(self):
        """Test getting unregistered model returns None."""
        model_class = ReferenceService.get_model_class("nonexistent", "Model")
        self.assertIsNone(model_class)
    
    def test_validate_reference_success(self):
        """Test successful reference validation."""
        result = self.service.validate_reference(
            app_name="assets",
            model_name="Asset",
            resource_id=str(self.asset.id),
            tenant_id=str(self.tenant.id)
        )
        self.assertTrue(result)
    
    def test_validate_reference_not_found(self):
        """Test reference validation with non-existent resource."""
        with self.assertRaises(NotFoundError):
            self.service.validate_reference(
                app_name="assets",
                model_name="Asset",
                resource_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id)
            )
    
    def test_validate_reference_wrong_tenant(self):
        """Test reference validation enforces tenant isolation."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE"
        )
        
        with self.assertRaises(NotFoundError):
            self.service.validate_reference(
                app_name="assets",
                model_name="Asset",
                resource_id=str(self.asset.id),
                tenant_id=str(other_tenant.id)
            )
    
    def test_validate_reference_unregistered_model(self):
        """Test reference validation with unregistered model."""
        with self.assertRaises(ValidationError) as cm:
            self.service.validate_reference(
                app_name="nonexistent",
                model_name="Model",
                resource_id=str(uuid.uuid4())
            )
        
        self.assertIn("not registered", str(cm.exception))
    
    def test_get_reference_success(self):
        """Test successful reference retrieval."""
        asset = self.service.get_reference(
            app_name="assets",
            model_name="Asset",
            resource_id=str(self.asset.id),
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(asset.id, self.asset.id)
        self.assertEqual(asset.name, self.asset.name)
    
    def test_get_reference_not_found(self):
        """Test reference retrieval with non-existent resource."""
        with self.assertRaises(NotFoundError):
            self.service.get_reference(
                app_name="assets",
                model_name="Asset",
                resource_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id)
            )
    
    def test_validate_multiple_references(self):
        """Test validating multiple references."""
        references = [
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": str(self.asset.id)
            },
            {
                "app_name": "files",
                "model_name": "File",
                "resource_id": str(self.file.id)
            }
        ]
        
        results = self.service.validate_multiple_references(
            references,
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[str(self.asset.id)])
        self.assertTrue(results[str(self.file.id)])
    
    def test_validate_multiple_references_with_invalid(self):
        """Test validating multiple references with some invalid."""
        references = [
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": str(self.asset.id)
            },
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": str(uuid.uuid4())  # Invalid
            }
        ]
        
        results = self.service.validate_multiple_references(
            references,
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[str(self.asset.id)])
        self.assertFalse(results[list(results.keys())[1]])


