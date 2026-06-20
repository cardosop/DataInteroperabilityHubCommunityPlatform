"""
Unit tests for AssetsBusinessRules dataset attachment validation.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.business_rules import AssetsBusinessRules
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetsBusinessRulesDatasetAttachmentTest(TestCase):
    """Test AssetsBusinessRules dataset attachment validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file for datasets
        from hub.apps.files.models import File, FileStatus

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
            status=FileStatus.ACTIVE,
        )

    def test_validate_dataset_attachment_tenant_ownership_valid(self):
        """Test dataset attachment validation with matching tenant"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["validation_checks"]["tenant_ownership"]["tenants_match"])

    def test_validate_dataset_attachment_tenant_ownership_mismatch(self):
        """Test dataset attachment validation with tenant mismatch"""
        from hub.apps.datasets.tests.factories import DatasetFactory
        from hub.apps.files.models import File, FileStatus

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create dataset with different tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/other/other.csv",
            status=FileStatus.ACTIVE,
        )
        dataset = DatasetFactory.create_dataset(tenant=other_tenant, file=other_file)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertFalse(result.is_valid)
        self.assertIn("tenant", result.errors[0].lower())
        self.assertFalse(result.details["validation_checks"]["tenant_ownership"]["tenants_match"])

    def test_validate_dataset_attachment_schema_compatibility_valid(self):
        """Test schema compatibility validation with matching schemas"""
        from hub.apps.contracts.models import (
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create contract with schema
        contract_schema_fields = [
            {"name": "id", "data_type": "string", "nullable": False},
            {"name": "value", "data_type": "string", "nullable": True},
        ]
        hub_contract_json = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=contract_schema_fields
        )

        ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract_json,
        )

        # Create dataset with matching schema
        dataset_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "string", "nullable": True},
            ]
        }

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, schema_json=dataset_schema
        )

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(
            result.details["validation_checks"]["schema_compatibility"]["schema_compatible"]
        )

    def test_validate_dataset_attachment_schema_compatibility_missing_fields(self):
        """Test schema compatibility validation with missing fields"""
        from hub.apps.contracts.models import (
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create contract with schema
        contract_schema_fields = [
            {"name": "id", "data_type": "string", "nullable": False},
            {"name": "value", "data_type": "string", "nullable": True},
            {"name": "required_field", "data_type": "string", "nullable": False},
        ]
        hub_contract_json = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=contract_schema_fields
        )

        ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract_json,
        )

        # Create dataset with missing field
        dataset_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "string", "nullable": True},
                # Missing "required_field"
            ]
        }

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, schema_json=dataset_schema
        )

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertFalse(result.is_valid)
        self.assertIn("missing", result.errors[0].lower())
        self.assertIn("required_field", result.errors[0])
        self.assertFalse(
            result.details["validation_checks"]["schema_compatibility"]["schema_compatible"]
        )

    def test_validate_dataset_attachment_schema_compatibility_type_mismatch(self):
        """Test schema compatibility validation with type mismatch"""
        from hub.apps.contracts.models import (
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create contract with schema
        contract_schema_fields = [
            {"name": "id", "data_type": "string", "nullable": False},
            {"name": "count", "data_type": "integer", "nullable": False},
        ]
        hub_contract_json = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=contract_schema_fields
        )

        ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract_json,
        )

        # Create dataset with incompatible type
        dataset_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "count", "type": "boolean", "nullable": False},  # Incompatible type
            ]
        }

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, schema_json=dataset_schema
        )

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertFalse(result.is_valid)
        self.assertIn("incompatible", result.errors[0].lower())
        self.assertIn("count", result.errors[0])

    def test_validate_dataset_attachment_schema_compatibility_no_contract(self):
        """Test schema compatibility validation when asset has no contract"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        # Should be valid (no contract = no schema check)
        self.assertTrue(result.is_valid)
        self.assertFalse(
            result.details["validation_checks"]["schema_compatibility"]["contract_exists"]
        )

    def test_validate_dataset_attachment_version_compatibility_valid(self):
        """Test version compatibility validation with valid version"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create first dataset version
        DatasetFactory.create_dataset(tenant=self.tenant, file=self.file, asset=asset, version=1)

        # Create second dataset
        dataset_v2 = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file, version=2)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset_v2, user=self.user, proposed_version=2
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(
            result.details["validation_checks"]["version_compatibility"]["version_valid"]
        )

    def test_validate_dataset_attachment_version_compatibility_invalid(self):
        """Test version compatibility validation with invalid version"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create first dataset version
        DatasetFactory.create_dataset(tenant=self.tenant, file=self.file, asset=asset, version=1)

        # Try to attach with version <= latest
        dataset_v2 = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            version=1,  # Same version
        )

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset_v2, user=self.user, proposed_version=1
        )

        self.assertFalse(result.is_valid)
        self.assertIn("greater than latest version", result.errors[0])
        self.assertFalse(
            result.details["validation_checks"]["version_compatibility"]["version_valid"]
        )

    def test_validate_dataset_attachment_version_compatibility_auto_increment(self):
        """Test version compatibility validation with auto-increment"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(
            asset=asset,
            dataset=dataset,
            user=self.user,
            proposed_version=None,  # Auto-increment
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(
            result.details["validation_checks"]["version_compatibility"]["auto_increment"]
        )

    def test_validate_dataset_attachment_access_same_tenant(self):
        """Test dataset access validation with same tenant"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["validation_checks"]["access"]["access_allowed"])
        self.assertFalse(result.details["validation_checks"]["access"]["cross_tenant"])

    def test_validate_dataset_attachment_access_no_user(self):
        """Test dataset access validation without user"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(asset=asset, dataset=dataset, user=None)

        # Should be valid (access check skipped)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["validation_checks"]["access"]["access_allowed"])

    # ========== EDGE CASES ==========

    def test_validate_dataset_attachment_edge_case_none_dataset(self):
        """Test dataset attachment validation with None dataset raises an error"""
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # None dataset must raise AttributeError or TypeError
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_dataset_attachment(asset=asset, dataset=None, user=self.user)

    def test_validate_dataset_attachment_edge_case_none_asset(self):
        """Test dataset attachment validation with None asset raises an error"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        # None asset must raise AttributeError or TypeError
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_dataset_attachment(asset=None, dataset=dataset, user=self.user)

    def test_validate_dataset_attachment_edge_case_none_user(self):
        """Test dataset attachment validation with None user succeeds (access check skipped)"""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        # None user is explicitly supported (see test_validate_dataset_attachment_access_no_user)
        result = self.rules.validate_dataset_attachment(asset=asset, dataset=dataset, user=None)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid)

    def test_validate_dataset_attachment_same_tenant_valid(self):
        """Dataset attachment with same tenant is valid and tenants_match."""
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        dataset = DatasetFactory.create_dataset(tenant=self.tenant, file=self.file)

        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(
            result.details["validation_checks"]["tenant_ownership"]["tenants_match"]
        )


class AssetsBusinessRulesDatasetAttachmentIntegrationTest(TestCase):
    """Integration tests for dataset attachment validation with DatasetService"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file for datasets
        from hub.apps.files.models import File, FileStatus

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
            status=FileStatus.ACTIVE,
        )

    def test_dataset_attachment_integration_with_real_dataset(self):
        """Integration test with real dataset model"""
        from hub.apps.contracts.models import (
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        from hub.apps.datasets.tests.factories import DatasetFactory

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create contract with schema
        contract_schema_fields = [
            {"name": "id", "data_type": "string", "nullable": False},
            {"name": "name", "data_type": "string", "nullable": True},
        ]
        hub_contract_json = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=contract_schema_fields
        )

        ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract_json,
        )

        # Create dataset using factory with matching schema
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
            format="CSV",
        )

        # Validate attachment
        result = self.rules.validate_dataset_attachment(
            asset=asset, dataset=dataset, user=self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["validation_checks"]["tenant_ownership"]["tenants_match"])
        self.assertTrue(
            result.details["validation_checks"]["schema_compatibility"]["schema_compatible"]
        )
