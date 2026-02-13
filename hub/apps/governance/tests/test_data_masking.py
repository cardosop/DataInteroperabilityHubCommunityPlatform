"""
Unit tests for Data Masking

Tests for masking strategies (redact, hash, partial, format-preserving)
and automatic masking based on classification and access level.
"""
import pytest
from django.test import TestCase

from hub.apps.governance.data_masking import DataMasker, MaskingStrategy
from hub.apps.governance.models import ClassificationCategory
from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
from hub.apps.governance.models import DataClassification
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class DataMaskerTest(TestCase):
    """Test DataMasker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_redact_strategy(self):
        """Test REDACT masking strategy"""
        value = "sensitive_data"
        masked = DataMasker.mask_value(value, MaskingStrategy.REDACT.value)
        
        self.assertEqual(masked, "***REDACTED***")
        
        # Test custom redact string
        config = {"redact_string": "***MASKED***"}
        masked = DataMasker.mask_value(value, MaskingStrategy.REDACT.value, config)
        self.assertEqual(masked, "***MASKED***")
    
    def test_hash_strategy(self):
        """Test HASH masking strategy"""
        value = "sensitive_data"
        masked = DataMasker.mask_value(value, MaskingStrategy.HASH.value)
        
        self.assertIsInstance(masked, str)
        self.assertEqual(len(masked), 64)  # SHA-256 hex digest length
        
        # Test MD5
        config = {"algorithm": "md5"}
        masked_md5 = DataMasker.mask_value(value, MaskingStrategy.HASH.value, config)
        self.assertEqual(len(masked_md5), 32)  # MD5 hex digest length
    
    def test_partial_strategy(self):
        """Test PARTIAL masking strategy"""
        value = "1234567890"
        masked = DataMasker.mask_value(value, MaskingStrategy.PARTIAL.value)
        
        self.assertEqual(masked, "******7890")  # Show last 4
        
        # Test custom show_chars
        config = {"show_chars": 2, "mask_char": "X"}
        masked = DataMasker.mask_value(value, MaskingStrategy.PARTIAL.value, config)
        self.assertEqual(masked, "XXXXXXXX90")
    
    def test_format_preserving_email(self):
        """Test FORMAT_PRESERVING strategy for email"""
        value = "user@example.com"
        masked = DataMasker.mask_value(value, MaskingStrategy.FORMAT_PRESERVING.value)
        
        self.assertIn("@", masked)
        self.assertIn("example.com", masked)
        self.assertNotEqual(masked, value)
    
    def test_format_preserving_phone(self):
        """Test FORMAT_PRESERVING strategy for phone"""
        value = "(123) 456-7890"
        masked = DataMasker.mask_value(value, MaskingStrategy.FORMAT_PRESERVING.value)
        
        self.assertIn("-", masked)
        self.assertIn("7890", masked)  # Last 4 digits
        self.assertNotEqual(masked, value)
    
    def test_format_preserving_ssn(self):
        """Test FORMAT_PRESERVING strategy for SSN"""
        value = "123-45-6789"
        masked = DataMasker.mask_value(value, MaskingStrategy.FORMAT_PRESERVING.value)
        
        self.assertEqual(masked, "***-**-6789")
    
    def test_format_preserving_credit_card(self):
        """Test FORMAT_PRESERVING strategy for credit card"""
        value = "1234-5678-9012-3456"
        masked = DataMasker.mask_value(value, MaskingStrategy.FORMAT_PRESERVING.value)
        
        self.assertIn("-", masked)
        self.assertIn("3456", masked)  # Last 4 digits
        self.assertNotEqual(masked, value)
    
    def test_mask_based_on_classification(self):
        """Test masking based on classification"""
        # PII should use format-preserving
        value = "user@example.com"
        masked = DataMasker.mask_based_on_classification(
            value,
            ClassificationCategory.PII
        )
        self.assertNotEqual(masked, value)
        self.assertIn("@", masked)
        
        # RESTRICTED should use redact
        masked = DataMasker.mask_based_on_classification(
            value,
            ClassificationCategory.RESTRICTED
        )
        self.assertEqual(masked, "***REDACTED***")
        
        # PUBLIC should not mask
        masked = DataMasker.mask_based_on_classification(
            value,
            ClassificationCategory.PUBLIC
        )
        self.assertEqual(masked, value)
    
    def test_mask_dataset_row(self):
        """Test masking a dataset row"""
        # Create access policy
        access_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # Create field policy with masking
        field_policy = FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=access_policy,
            dataset=self.dataset,
            field_name="email",
            access_type="READ",
            masking_strategy="FORMAT_PRESERVING",
            masking_config={"show_last": 4},
        )
        
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        row = {
            "email": "user@example.com",
            "name": "John Doe"
        }
        
        masked_row = DataMasker.mask_dataset_row(
            row=row,
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            access_type="READ"
        )
        
        # Email should be masked
        self.assertNotEqual(masked_row["email"], row["email"])
        self.assertIn("@", masked_row["email"])
        
        # Name should not be masked (no policy)
        self.assertEqual(masked_row["name"], row["name"])

