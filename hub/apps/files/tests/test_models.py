"""
Unit tests for File model.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.files.models import File, FileStatus

User = get_user_model()


class FileModelTest(TestCase):
    """Test File model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_create_file(self):
        """Test file creation"""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.UPLOADING,
            created_by=self.user
        )
        
        self.assertEqual(file_obj.tenant, self.tenant)
        self.assertEqual(file_obj.name, "test.csv")
        self.assertEqual(file_obj.size, 1024)
        self.assertEqual(file_obj.status, FileStatus.UPLOADING)
    
    def test_file_status_choices(self):
        """Test file status enum"""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
        )
        
        file_obj.status = FileStatus.COMPLETED
        file_obj.save()
        self.assertEqual(file_obj.status, FileStatus.COMPLETED)

