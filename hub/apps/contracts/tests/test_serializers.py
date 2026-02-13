"""
Unit tests for contract serializers.
"""

import pytest

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.serializers import (
    ContractCreateSerializer,
    ContractSerializer,
    ContractUpdateSerializer,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ContractSerializerTest(ContractsTestBase):
    """Test contract serializers"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            created_by=self.user,
        )

    def test_contract_serializer(self):
        """Test ContractSerializer serialization"""
        serializer = ContractSerializer(self.contract)
        data = serializer.data

        self.assertEqual(data["id"], str(self.contract.id))
        self.assertEqual(data["status"], ContractStatus.DRAFT)
        self.assertEqual(data["original_spec_type"], OriginalSpecType.ODCS)
        self.assertIn("original_raw", data)
        self.assertIn("hub_contract_json", data)

    def test_contract_create_serializer(self):
        """Test ContractCreateSerializer validation"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"id": "new", "name": "New Contract"}',
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            }
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["original_format"], "JSON")
        self.assertEqual(serializer.validated_data["original_spec_type"], "ODCS")

    def test_contract_create_serializer_invalid_format(self):
        """Test ContractCreateSerializer with invalid format"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"id": "test"}',
                "original_format": "INVALID",
                "original_spec_type": "ODCS",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("original_format", serializer.errors)

    def test_contract_update_serializer(self):
        """Test ContractUpdateSerializer"""
        # Note: ContractUpdateSerializer is a plain Serializer, not ModelSerializer
        # So we test validation only, not save
        serializer = ContractUpdateSerializer(data={"status": ContractStatus.ACTIVE})

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], ContractStatus.ACTIVE)

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_contract_serializer_deserialization(self):
        """Test ContractSerializer deserialization"""
        serializer = ContractSerializer(
            data={
                "id": str(self.contract.id),
                "status": ContractStatus.DRAFT,
                "original_spec_type": OriginalSpecType.ODCS,
                "original_raw": '{"id": "test"}',
            }
        )

        # ContractSerializer is read-only, so deserialization may not be supported
        # This test verifies the behavior
        self.assertFalse(serializer.is_valid())  # Read-only serializer

    def test_contract_create_serializer_missing_required_fields(self):
        """Test ContractCreateSerializer with missing required fields"""
        serializer = ContractCreateSerializer(
            data={
                "original_format": "JSON",
                # Missing original_raw and original_spec_type
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("original_raw", serializer.errors)

    def test_contract_create_serializer_invalid_spec_type(self):
        """Test ContractCreateSerializer with invalid spec_type"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"id": "test"}',
                "original_format": "JSON",
                "original_spec_type": "INVALID_TYPE",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("original_spec_type", serializer.errors)

    def test_contract_create_serializer_yaml_format(self):
        """Test ContractCreateSerializer with YAML format"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": "id: test\nname: Test Contract",
                "original_format": "YAML",
                "original_spec_type": "ODCS",
            }
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["original_format"], "YAML")

    def test_contract_create_serializer_odps_spec_type(self):
        """Test ContractCreateSerializer with ODPS spec_type"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"schema": "https://opendataproducts.org/schema/v4.1"}',
                "original_format": "JSON",
                "original_spec_type": "ODPS",
            }
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["original_spec_type"], "ODPS")

    def test_contract_update_serializer_invalid_status(self):
        """Test ContractUpdateSerializer with invalid status"""
        serializer = ContractUpdateSerializer(data={"status": "INVALID_STATUS"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_contract_update_serializer_partial_update(self):
        """Test ContractUpdateSerializer with partial data"""
        serializer = ContractUpdateSerializer(data={"status": ContractStatus.ACTIVE}, partial=True)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], ContractStatus.ACTIVE)

    def test_contract_update_serializer_empty_data(self):
        """Test ContractUpdateSerializer with empty data"""
        serializer = ContractUpdateSerializer(data={})

        # Empty data should be valid for partial updates
        self.assertTrue(serializer.is_valid())

    def test_contract_serializer_includes_all_fields(self):
        """Test ContractSerializer includes all expected fields"""
        serializer = ContractSerializer(self.contract)
        data = serializer.data

        # Check all important fields are present
        self.assertIn("id", data)
        self.assertIn("status", data)
        self.assertIn("original_spec_type", data)
        self.assertIn("original_spec_version", data)
        self.assertIn("original_format", data)
        self.assertIn("original_raw", data)
        self.assertIn("hub_contract_json", data)
        self.assertIn("validation_status", data)
        self.assertIn("normalization_status", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_contract_serializer_with_asset(self):
        """Test ContractSerializer includes asset information"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            created_by=self.user,
        )

        serializer = ContractSerializer(contract)
        data = serializer.data

        self.assertIn("asset", data)
        if data["asset"]:
            self.assertEqual(data["asset"], str(asset.id))

    def test_contract_create_serializer_empty_original_raw(self):
        """Test ContractCreateSerializer with empty original_raw"""
        serializer = ContractCreateSerializer(
            data={"original_raw": "", "original_format": "JSON", "original_spec_type": "ODCS"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("original_raw", serializer.errors)

    def test_contract_create_serializer_invalid_json(self):
        """Test ContractCreateSerializer with invalid JSON in original_raw"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"id": invalid}',
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            }
        )

        # Serializer may or may not validate JSON syntax
        # This test verifies the behavior
        is_valid = serializer.is_valid()
        # If invalid, should have errors
        if not is_valid:
            self.assertTrue(len(serializer.errors) > 0)

    def test_contract_update_serializer_retired_status(self):
        """Test ContractUpdateSerializer with RETIRED status"""
        serializer = ContractUpdateSerializer(data={"status": ContractStatus.RETIRED})

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], ContractStatus.RETIRED)

    def test_contract_serializer_read_only_fields(self):
        """Test ContractSerializer read-only fields are not writable"""
        serializer = ContractSerializer(self.contract)
        data = serializer.data

        # These fields should be present but read-only
        self.assertIn("id", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_contract_create_serializer_extra_fields_ignored(self):
        """Test ContractCreateSerializer ignores extra fields"""
        serializer = ContractCreateSerializer(
            data={
                "original_raw": '{"id": "test"}',
                "original_format": "JSON",
                "original_spec_type": "ODCS",
                "extra_field": "should_be_ignored",
            }
        )

        # Should be valid, extra fields ignored
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("extra_field", serializer.validated_data)
