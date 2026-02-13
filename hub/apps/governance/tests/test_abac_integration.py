"""
Integration tests for ABAC

Tests for policy evaluation with real data classifications and field policies.
"""
import pytest
from django.test import TestCase

from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
from hub.apps.governance.abac import ABACEngine
from hub.apps.governance.models import DataClassification, ClassificationCategory
from hub.apps.governance.data_masking import DataMasker
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ABACIntegrationTest(TestCase):
    """Integration tests for ABAC"""
    
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
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]},
                    {"name": "name", "data_type": "string", "sample_values": ["John Doe"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_abac_with_classification_and_masking(self):
        """Test ABAC with classification and masking"""
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        # Create access policy
        access_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow PII Access",
            conditions={
                "resource": {"classification": ClassificationCategory.PII.value}
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
        
        # Evaluate access
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ",
            field_name="email"
        )
        
        self.assertTrue(result.allowed)
        self.assertTrue(result.masking_required)
        
        # Test masking
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
        
        # Name should not be masked
        self.assertEqual(masked_row["name"], row["name"])

