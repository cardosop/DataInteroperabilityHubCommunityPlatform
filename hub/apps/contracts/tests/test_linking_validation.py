"""
Unit tests for contract linking validation (Task 3.1.3)

Tests:
- Contract existence validation
- Contract compatibility validation
- Circular reference prevention
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.linking_validation import (
    validate_contract_exists,
    validate_contract_compatibility,
    validate_no_circular_reference,
    validate_linking,
    LinkingValidationError
)

User = get_user_model()


class LinkingValidationTest(TestCase):
    """Test contract existence and compatibility validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create valid ODPS contract
        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{"schema": "https://opendataproducts.org/schema/v4.1"}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "test-odps",
                "info": {"name": "Test ODPS Product"},
                "schema": {"fields": []},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        # Create valid ODCS contract
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "test-odcs",
                "info": {"name": "Test ODCS Contract"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

    def test_validate_contract_exists_success(self):
        """Test successful contract existence validation."""
        contract = validate_contract_exists(str(self.odps_contract.id))
        self.assertEqual(contract.id, self.odps_contract.id)

    def test_validate_contract_exists_with_tenant_success(self):
        """Test successful contract existence validation with tenant check."""
        contract = validate_contract_exists(
            str(self.odps_contract.id),
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(contract.id, self.odps_contract.id)

    def test_validate_contract_exists_not_found(self):
        """Test contract existence validation fails for non-existent contract."""
        fake_id = str(uuid.uuid4())
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists(fake_id)

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")
        self.assertIn(fake_id, cm.exception.message)

    def test_validate_contract_exists_tenant_mismatch(self):
        """Test contract existence validation fails for wrong tenant."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists(
                str(self.odps_contract.id),
                tenant_id=str(other_tenant.id)
            )

        self.assertEqual(cm.exception.error_code, "TENANT_MISMATCH")

    def test_validate_contract_compatibility_success(self):
        """Test successful contract compatibility validation."""
        # Should not raise
        validate_contract_compatibility(self.odps_contract, self.odcs_contract)

    def test_validate_contract_compatibility_wrong_odps_type(self):
        """Test compatibility validation fails for wrong ODPS type."""
        wrong_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,  # Wrong type
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "wrong", "info": {"name": "Wrong"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(wrong_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("ODPS", cm.exception.context["errors"][0])

    def test_validate_contract_compatibility_wrong_odcs_type(self):
        """Test compatibility validation fails for wrong ODCS type."""
        wrong_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,  # Wrong type
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "wrong", "info": {"name": "Wrong"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, wrong_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("ODCS", cm.exception.context["errors"][0])

    def test_validate_contract_compatibility_tenant_mismatch(self):
        """Test compatibility validation fails for different tenants."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )
        other_odcs = Contract.objects.create(
            tenant=other_tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "other", "info": {"name": "Other"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, other_odcs)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("tenant", cm.exception.context["errors"][0].lower())

    def test_validate_contract_compatibility_missing_hub_contract_odps(self):
        """Test compatibility validation fails when ODPS contract missing hub_contract_json."""
        self.odps_contract.hub_contract_json = None
        self.odps_contract.save()

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("hub_contract_json", cm.exception.context["errors"][0])

    def test_validate_contract_compatibility_missing_hub_contract_odcs(self):
        """Test compatibility validation fails when ODCS contract missing hub_contract_json."""
        self.odcs_contract.hub_contract_json = None
        self.odcs_contract.save()

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("hub_contract_json", cm.exception.context["errors"][0])

    def test_validate_contract_compatibility_not_normalized_odps(self):
        """Test compatibility validation fails when ODPS contract not normalized."""
        self.odps_contract.normalization_status = NormalizationStatus.NORMALIZATION_FAILED
        self.odps_contract.save()

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("normalized", cm.exception.context["errors"][0].lower())

    def test_validate_contract_compatibility_not_normalized_odcs(self):
        """Test compatibility validation fails when ODCS contract not normalized."""
        self.odcs_contract.normalization_status = NormalizationStatus.NORMALIZATION_FAILED
        self.odcs_contract.save()

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("normalized", cm.exception.context["errors"][0].lower())

    def test_validate_linking_success(self):
        """Test successful comprehensive linking validation."""
        odps, odcs = validate_linking(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(odps.id, self.odps_contract.id)
        self.assertEqual(odcs.id, self.odcs_contract.id)


class CircularReferencePreventionTest(TestCase):
    """Test circular reference prevention (Task 3.1.3)."""

    def setUp(self):
        """Set up test fixtures with linked contracts."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create base contracts
        self.odps1 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odps1",
                "info": {"name": "ODPS 1"},
                "schema": {"fields": []},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        self.odcs1 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odcs1",
                "info": {"name": "ODCS 1"},
                "schema": {"fields": []},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        # Create additional contracts for chain testing
        self.odps2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odps2",
                "info": {"name": "ODPS 2"},
                "schema": {"fields": []},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

        self.odcs2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odcs2",
                "info": {"name": "ODCS 2"},
                "schema": {"fields": []},
                "extensions": {}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )

    def test_validate_no_circular_reference_new_link(self):
        """Test that new links don't create circular references."""
        # Should not raise for new links
        validate_no_circular_reference(
            str(self.odps1.id),
            str(self.odcs1.id)
        )

    def test_validate_no_circular_reference_direct_cycle(self):
        """Test that direct circular reference is detected."""
        # Link ODPS1 -> ODCS1
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs1.id)
        }
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps1.id)
        }
        self.odcs1.save()

        # Try to link ODCS1 -> ODPS1 again (would create cycle)
        with self.assertRaises(LinkingValidationError) as cm:
            validate_no_circular_reference(
                str(self.odps1.id),
                str(self.odcs1.id)
            )

        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

    def test_validate_no_circular_reference_indirect_cycle(self):
        """Test that indirect circular reference is detected."""
        # Create chain: ODPS1 -> ODCS1 -> ODPS2 -> ODCS2
        # Then try to link ODCS2 -> ODPS1 (would create cycle)

        # Link ODPS1 -> ODCS1
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs1.id)
        }
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps1.id)
        }
        self.odcs1.save()

        # Link ODPS2 -> ODCS2
        self.odps2.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs2.id)
        }
        self.odps2.save()

        self.odcs2.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps2.id)
        }
        self.odcs2.save()

        # Link ODCS1 -> ODPS2 (creating chain)
        self.odcs1.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(self.odps2.id)
        self.odcs1.save()

        # Now try to link ODCS2 -> ODPS1 (would create cycle: ODPS1 -> ODCS1 -> ODPS2 -> ODCS2 -> ODPS1)
        with self.assertRaises(LinkingValidationError) as cm:
            validate_no_circular_reference(
                str(self.odps1.id),
                str(self.odcs2.id)
            )

        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

    def test_validate_no_circular_reference_valid_chain(self):
        """Test that valid chains don't trigger false positives."""
        # Create valid chain: ODPS1 -> ODCS1, ODPS2 -> ODCS2 (no cycles)
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs1.id)
        }
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps1.id)
        }
        self.odcs1.save()

        # Should not raise for linking ODPS2 -> ODCS2 (separate chain)
        validate_no_circular_reference(
            str(self.odps2.id),
            str(self.odcs2.id)
        )

    def test_validate_linking_with_circular_reference(self):
        """Test that comprehensive validation catches circular references."""
        # Link ODPS1 -> ODCS1
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs1.id)
        }
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps1.id)
        }
        self.odcs1.save()

        # Try to link again (would create cycle)
        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=str(self.odps1.id),
                odcs_contract_id=str(self.odcs1.id),
                tenant_id=str(self.tenant.id)
            )

        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

