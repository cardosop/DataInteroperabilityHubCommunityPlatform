"""
Unit tests for Data Classification

Tests for rule-based classifier, field/dataset/asset-level classification,
confidence scoring, and manual review workflow.
"""
import pytest
from django.test import TestCase

from hub.apps.governance.models import (
    DataClassification,
    ClassificationCategory,
    ClassificationStatus
)
from hub.apps.governance.classification import (
    DataClassifier,
    ClassificationResult
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class DataClassifierTest(TestCase):
    """Test DataClassifier"""
    
    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
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
    
    def test_classify_field_email(self):
        """Test email field classification"""
        result = DataClassifier.classify_field(
            field_name="email",
            sample_values=["user@example.com", "admin@test.com"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.PII)
        self.assertGreater(result.confidence, 0.9)
        self.assertIn("email_detection", result.matched_rules)
        self.assertIn("EMAIL", result.pii_types)
    
    def test_classify_field_phone(self):
        """Test phone field classification"""
        result = DataClassifier.classify_field(
            field_name="phone_number",
            sample_values=["123-456-7890", "+1-555-123-4567"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.PII)
        self.assertGreater(result.confidence, 0.8)
        self.assertIn("phone_detection", result.matched_rules)
    
    def test_classify_field_ssn(self):
        """Test SSN field classification"""
        result = DataClassifier.classify_field(
            field_name="ssn",
            sample_values=["123-45-6789"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.PII)
        self.assertGreater(result.confidence, 0.95)
        self.assertIn("ssn_detection", result.matched_rules)
        self.assertIn("SSN", result.pii_types)
    
    def test_classify_field_credit_card(self):
        """Test credit card field classification"""
        result = DataClassifier.classify_field(
            field_name="credit_card",
            sample_values=["1234-5678-9012-3456"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.PCI)
        self.assertGreater(result.confidence, 0.9)
        self.assertIn("credit_card_detection", result.matched_rules)
    
    def test_classify_field_financial(self):
        """Test financial field classification"""
        result = DataClassifier.classify_field(
            field_name="salary",
            sample_values=["50000", "75000"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.FINANCIAL)
        self.assertGreater(result.confidence, 0.7)
    
    def test_classify_field_default(self):
        """Test default classification for unknown field"""
        result = DataClassifier.classify_field(
            field_name="unknown_field",
            sample_values=["value1", "value2"]
        )
        
        self.assertEqual(result.category, ClassificationCategory.INTERNAL)
        self.assertEqual(result.confidence, 0.5)
    
    def test_classify_field_level(self):
        """Test field-level classification creation"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        classification = DataClassifier.classify_field_level(
            tenant_id=str(self.tenant.id),
            dataset_id=str(dataset.id),
            field_name="email",
            field_data={"name": "email", "data_type": "string"},
            sample_values=["user@example.com"],
            user_id=str(self.user.id)
        )
        
        self.assertIsNotNone(classification)
        self.assertEqual(classification.category, ClassificationCategory.PII.value)
        self.assertEqual(classification.status, ClassificationStatus.AUTO_CLASSIFIED.value)
        self.assertIsNotNone(classification.confidence_score)
        self.assertGreater(classification.confidence_score, 0.9)
    
    def test_classify_dataset(self):
        """Test dataset-level classification"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]},
                    {"name": "phone", "data_type": "string", "sample_values": ["123-456-7890"]},
                    {"name": "name", "data_type": "string", "sample_values": ["John Doe"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        classifications = DataClassifier.classify_dataset(
            tenant_id=str(self.tenant.id),
            dataset_id=str(dataset.id),
            user_id=str(self.user.id)
        )
        
        self.assertEqual(len(classifications), 3)
        
        email_class = next(c for c in classifications if c.field_name == "email")
        self.assertEqual(email_class.category, ClassificationCategory.PII.value)
        
        phone_class = next(c for c in classifications if c.field_name == "phone")
        self.assertEqual(phone_class.category, ClassificationCategory.PII.value)
    
    def test_classify_asset(self):
        """Test asset-level classification"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]}
                ]
            },
            format="CSV",
            version=1,
            is_current=True,
            created_by=self.user
        )
        
        classifications = DataClassifier.classify_asset(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            user_id=str(self.user.id)
        )
        
        self.assertGreater(len(classifications), 0)
        self.assertTrue(any(c.field_name == "email" for c in classifications))
    
    def test_approve_classification(self):
        """Test classification approval"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        classification = DataClassifier.classify_field_level(
            tenant_id=str(self.tenant.id),
            dataset_id=str(dataset.id),
            field_name="email",
            field_data={"name": "email", "data_type": "string"},
            sample_values=["user@example.com"],
            user_id=str(self.user.id)
        )
        
        # Approve classification
        approved = DataClassifier.approve_classification(
            classification_id=str(classification.id),
            user_id=str(self.user.id),
            notes="Approved after review"
        )
        
        self.assertEqual(approved.status, ClassificationStatus.APPROVED.value)
        self.assertEqual(approved.reviewed_by, self.user)
        self.assertIsNotNone(approved.reviewed_at)
        self.assertEqual(approved.manual_review_notes, "Approved after review")
    
    def test_reject_classification(self):
        """Test classification rejection"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        classification = DataClassifier.classify_field_level(
            tenant_id=str(self.tenant.id),
            dataset_id=str(dataset.id),
            field_name="email",
            field_data={"name": "email", "data_type": "string"},
            sample_values=["user@example.com"],
            user_id=str(self.user.id)
        )
        
        # Reject and set new category
        rejected = DataClassifier.reject_classification(
            classification_id=str(classification.id),
            user_id=str(self.user.id),
            new_category=ClassificationCategory.INTERNAL,
            notes="False positive, not PII"
        )
        
        self.assertEqual(rejected.status, ClassificationStatus.REJECTED.value)
        self.assertEqual(rejected.category, ClassificationCategory.INTERNAL.value)
        self.assertEqual(rejected.reviewed_by, self.user)
        self.assertIsNotNone(rejected.reviewed_at)

