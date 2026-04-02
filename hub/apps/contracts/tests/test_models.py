"""
Unit tests for Contract model.
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

from django.core.exceptions import ValidationError

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase


class ContractModelTest(ContractsTestBase):
    """Test Contract model"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_create_contract(self):
        """Test contract creation"""
        # Arrange & Act
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Assert
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.status, ContractStatus.DRAFT)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODCS)

    def test_contract_status_choices(self):
        """Test contract status enum"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        contract.status = ContractStatus.ACTIVE
        contract.save()
        self.assertEqual(contract.status, ContractStatus.ACTIVE)

    def test_contract_clean_validation(self):
        """Test contract clean() validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        # DRAFT status should not require validation
        contract.clean()

        # ACTIVE status requires valid validation and normalization
        contract.status = ContractStatus.ACTIVE
        contract.validation_status = ValidationStatus.INVALID
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK

        with self.assertRaises(ValidationError):
            contract.clean()

    def test_can_activate(self):
        """Test can_activate method"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")

        # Invalid validation status
        contract.validation_status = ValidationStatus.INVALID
        contract.save()
        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

    def test_original_spec_type_odps_enum(self):
        """Test that ODPS is a valid OriginalSpecType enum value"""
        # Verify ODPS is in the enum choices
        choices = [choice[0] for choice in OriginalSpecType.choices]
        self.assertIn(OriginalSpecType.ODPS, choices)
        self.assertIn(OriginalSpecType.ODCS, choices)

        # Verify ODPS value and label
        self.assertEqual(OriginalSpecType.ODPS, "ODPS")
        self.assertEqual(OriginalSpecType.ODPS.label, "ODPS")

        # Verify ODPS can be used to create a contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-odps", "name": "Test ODPS Contract"}',
        )

        # Verify the contract was created with ODPS
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(contract.original_spec_type, "ODPS")

        # Verify the contract can be retrieved from database
        retrieved_contract = Contract.objects.get(id=contract.id)
        self.assertEqual(retrieved_contract.original_spec_type, OriginalSpecType.ODPS)

        # Verify ODPS can be updated
        contract.original_spec_type = OriginalSpecType.ODCS
        contract.save()
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODCS)

        # Verify ODPS can be set back
        contract.original_spec_type = OriginalSpecType.ODPS
        contract.save()
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODPS)

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_contract_retired_status(self):
        """Test RETIRED status can be set"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        contract.status = ContractStatus.RETIRED
        contract.save()
        self.assertEqual(contract.status, ContractStatus.RETIRED)

    def test_contract_clean_with_invalid_hub_contract_json(self):
        """Test clean() validation with invalid hub_contract_json"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        # Set invalid hub_contract_json (missing required fields)
        contract.hub_contract_json = {"invalid": "structure"}
        with self.assertRaises(ValidationError):
            contract.clean()

    def test_contract_clean_with_wrong_hub_contract_version(self):
        """Test clean() validation with wrong hub_contract_version"""
        from hub.apps.contracts.versioning import get_default_version

        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        # Set hub_contract_json with wrong version
        default_version = get_default_version()
        wrong_version = "999.0.0" if default_version != "999.0.0" else "998.0.0"
        contract.hub_contract_json = {
            "hub_contract_version": wrong_version,
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": []},
        }
        with self.assertRaises(ValidationError):
            contract.clean()

    def test_contract_can_activate_with_warning_only(self):
        """Test can_activate with WARNING_ONLY validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        )

        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")

    def test_contract_can_activate_with_normalization_warnings(self):
        """Test can_activate with NORMALIZED_WITH_WARNINGS"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        )

        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")

    def test_contract_can_activate_with_not_normalized(self):
        """Test can_activate fails with NOT_NORMALIZED"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("normalization_status", reason)

    def test_contract_can_activate_with_normalization_failed(self):
        """Test can_activate fails with NORMALIZATION_FAILED"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("normalization_status", reason)

    def test_contract_can_activate_with_error_validation_status(self):
        """Test can_activate fails with ERROR validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.ERROR,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

    def test_contract_clean_active_with_warning_only_validation(self):
        """Test clean() allows ACTIVE with WARNING_ONLY validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        contract.status = ContractStatus.ACTIVE
        # Should not raise ValidationError
        contract.clean()

    def test_contract_clean_active_with_normalization_warnings(self):
        """Test clean() allows ACTIVE with NORMALIZED_WITH_WARNINGS"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        )

        contract.status = ContractStatus.ACTIVE
        # Should not raise ValidationError
        contract.clean()

    def test_contract_with_asset_relationship(self):
        """Test contract relationship with asset"""
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
        )

        self.assertEqual(contract.asset, asset)
        self.assertEqual(contract.asset_id, asset.id)
        # Verify reverse relationship
        self.assertIn(contract, asset.contracts.all())

    def test_contract_without_asset(self):
        """Test contract can be created without asset (nullable)"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=None,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        self.assertIsNone(contract.asset)
        self.assertIsNone(contract.asset_id)

    def test_contract_validation_errors_jsonfield(self):
        """Test validation_errors JSONField stores list correctly"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_errors=["Error 1", "Error 2"],
        )

        self.assertEqual(contract.validation_errors, ["Error 1", "Error 2"])

    def test_contract_normalization_errors_jsonfield(self):
        """Test normalization_errors JSONField stores list correctly"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            normalization_errors=["Normalization error"],
        )

        self.assertEqual(contract.normalization_errors, ["Normalization error"])

    def test_contract_validation_warnings_jsonfield(self):
        """Test validation_warnings JSONField stores list correctly"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_warnings=["Warning 1"],
        )

        self.assertEqual(contract.validation_warnings, ["Warning 1"])

    def test_contract_normalization_warnings_jsonfield(self):
        """Test normalization_warnings JSONField stores list correctly"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            normalization_warnings=["Normalization warning"],
        )

        self.assertEqual(contract.normalization_warnings, ["Normalization warning"])

    def test_contract_str_representation(self):
        """Test __str__ method representation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        str_repr = str(contract)
        self.assertIn("No Asset", str_repr)  # No asset
        self.assertIn("ODCS", str_repr)
        self.assertIn("DRAFT", str_repr)

    def test_contract_str_representation_with_asset(self):
        """Test __str__ method representation with asset"""
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
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        str_repr = str(contract)
        self.assertIn("Test Asset", str_repr)
        self.assertIn("ODPS", str_repr)
        self.assertIn("ACTIVE", str_repr)

    def test_contract_version_default(self):
        """Test version field defaults to 1"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        self.assertEqual(contract.version, 1)

    def test_contract_status_default(self):
        """Test status field defaults to DRAFT"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        self.assertEqual(contract.status, ContractStatus.DRAFT)

    def test_contract_normalization_status_default(self):
        """Test normalization_status defaults to NOT_NORMALIZED"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )

        self.assertEqual(contract.normalization_status, NormalizationStatus.NOT_NORMALIZED)

    def test_contract_original_format_yaml(self):
        """Test contract can be created with YAML format"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.YAML,
            original_raw="id: test\nname: Test Contract",
        )

        self.assertEqual(contract.original_format, OriginalFormat.YAML)

    def test_contract_original_raw_resolved_nullable(self):
        """Test original_raw_resolved can be null"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            original_raw_resolved=None,
        )

        self.assertIsNone(contract.original_raw_resolved)

    def test_contract_original_raw_resolved_with_value(self):
        """Test original_raw_resolved can store resolved content"""
        resolved_content = '{"id": "test", "$ref": "resolved"}'
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "$ref": "#/definitions/test"}',
            original_raw_resolved=resolved_content,
        )

        self.assertEqual(contract.original_raw_resolved, resolved_content)
