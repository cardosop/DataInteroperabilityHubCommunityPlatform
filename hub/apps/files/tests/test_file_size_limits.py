"""
Unit tests for file size limits and validation.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.exceptions import ValidationError
from django.conf import settings

from hub.apps.files.validators import validate_file_size, validate_file_type
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FileSizeLimitsTest(TestCase):
    """Test file size limits and validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_validate_file_size_browser_within_limit(self):
        """Test file size validation for browser upload within limit"""
        size = settings.MAX_BROWSER_UPLOAD_SIZE - 1
        
        # Should not raise exception
        try:
            validate_file_size(size, "browser")
        except ValidationError:
            self.fail("validate_file_size raised ValidationError for valid size")
    
    def test_validate_file_size_browser_exceeds_limit(self):
        """Test file size validation for browser upload exceeding limit"""
        size = settings.MAX_BROWSER_UPLOAD_SIZE + 1
        
        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "browser")
        
        self.assertIn("browser upload limit", str(cm.exception))
    
    def test_validate_file_size_sdk_within_limit(self):
        """Test file size validation for SDK upload within limit"""
        size = settings.MAX_SDK_UPLOAD_SIZE - 1
        
        # Should not raise exception
        try:
            validate_file_size(size, "sdk")
        except ValidationError:
            self.fail("validate_file_size raised ValidationError for valid size")
    
    def test_validate_file_size_sdk_exceeds_limit(self):
        """Test file size validation for SDK upload exceeding limit"""
        size = settings.MAX_SDK_UPLOAD_SIZE + 1
        
        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "sdk")
        
        self.assertIn("SDK upload limit", str(cm.exception))
    
    def test_validate_file_size_exceeds_global_max(self):
        """Test file size validation exceeding global maximum"""
        size = settings.MAX_FILE_SIZE + 1
        
        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "browser")
        
        self.assertIn("global maximum", str(cm.exception))
    
    def test_validate_file_type_allowed(self):
        """Test file type validation for allowed types"""
        # Should not raise exception for allowed types
        allowed_types = settings.ALLOWED_FILE_TYPES
        
        for ext in allowed_types:
            try:
                validate_file_type(f"test.{ext}")
            except ValidationError:
                self.fail(f"validate_file_type raised ValidationError for allowed type: {ext}")
    
    def test_validate_file_type_not_allowed(self):
        """Test file type validation for disallowed types"""
        with self.assertRaises(ValidationError) as cm:
            validate_file_type("test.exe")
        
        self.assertIn("not allowed", str(cm.exception))
    
    def test_validate_file_type_no_extension(self):
        """Test file type validation for file without extension"""
        with self.assertRaises(ValidationError) as cm:
            validate_file_type("testfile")
        
        self.assertIn("extension", str(cm.exception))
    
    def test_init_upload_browser_size_limit(self):
        """Test upload initialization enforces browser size limit"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": settings.MAX_BROWSER_UPLOAD_SIZE + 1,
            "upload_method": "browser"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("size", response.data)
    
    def test_init_upload_sdk_size_limit(self):
        """Test upload initialization enforces SDK size limit"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "huge.csv",
            "content_type": "text/csv",
            "size": settings.MAX_SDK_UPLOAD_SIZE + 1,
            "upload_method": "sdk"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("size", response.data)
    
    def test_init_upload_global_size_limit(self):
        """Test upload initialization enforces global size limit"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "massive.csv",
            "content_type": "text/csv",
            "size": settings.MAX_FILE_SIZE + 1,
            "upload_method": "sdk"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("size", response.data)
    
    def test_init_upload_file_type_validation(self):
        """Test upload initialization validates file type"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "test.exe",
            "content_type": "application/x-msdownload",
            "size": 1024,
            "upload_method": "browser"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type", str(response.data).lower())

