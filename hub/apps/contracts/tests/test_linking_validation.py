"""
Unit tests for contract linking validation (Task 3.1.3)

Tests:
- Contract existence validation
- Contract compatibility validation
- Circular reference prevention
"""

import uuid

from hub.apps.contracts.linking_validation import (
    LinkingValidationError,
    validate_contract_compatibility,
    validate_contract_exists,
    validate_linking,
    validate_no_circular_reference,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.tenants.models import Tenant


class LinkingValidationTest(ContractsTestBase):
    """Test contract existence and compatibility validation."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

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
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
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
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

    def test_validate_contract_exists_success(self):
        """Test successful contract existence validation."""
        contract = validate_contract_exists(
            str(self.odps_contract.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(contract.id, self.odps_contract.id)

    def test_validate_contract_exists_with_tenant_success(self):
        """Test successful contract existence validation with tenant check."""
        contract = validate_contract_exists(
            str(self.odps_contract.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(contract.id, self.odps_contract.id)

    def test_validate_contract_exists_requires_tenant_id(self):
        """tenant_id is required for all contract existence checks."""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists(str(self.odps_contract.id), tenant_id=None)
        self.assertEqual(cm.exception.error_code, "TENANT_ID_REQUIRED")

    def test_validate_contract_exists_not_found(self):
        """Test contract existence validation fails for non-existent contract."""
        fake_id = str(uuid.uuid4())
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists(fake_id, tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")
        self.assertIn(fake_id, cm.exception.message)

    def test_validate_contract_exists_tenant_mismatch(self):
        """Test contract existence validation fails for wrong tenant."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists(str(self.odps_contract.id), tenant_id=str(other_tenant.id))

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
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "wrong", "info": {"name": "Wrong"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
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
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "wrong", "info": {"name": "Wrong"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, wrong_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertIn("ODCS", cm.exception.context["errors"][0])

    def test_validate_contract_compatibility_tenant_mismatch(self):
        """Test compatibility validation fails for different tenants."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_odcs = Contract.objects.create(
            tenant=other_tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "other", "info": {"name": "Other"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, other_odcs)

        self.assertIn(cm.exception.error_code, ["TENANT_MISMATCH", "INCOMPATIBLE_CONTRACTS"])
        error_str = str(cm.exception.context.get("errors", [cm.exception.message])).lower()
        self.assertIn("tenant", error_str)

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
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(odps.id, self.odps_contract.id)
        self.assertEqual(odcs.id, self.odcs_contract.id)


class CircularReferencePreventionTest(ContractsTestBase):
    """Test circular reference prevention (Task 3.1.3)."""

    def setUp(self):
        """Set up test fixtures with linked contracts."""
        super().setUp()

        # Create base contracts
        self.odps1 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odps1",
                "info": {"name": "ODPS 1"},
                "schema": {"fields": []},
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        self.odcs1 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odcs1",
                "info": {"name": "ODCS 1"},
                "schema": {"fields": []},
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Create additional contracts for chain testing
        self.odps2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odps2",
                "info": {"name": "ODPS 2"},
                "schema": {"fields": []},
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        self.odcs2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "id": "odcs2",
                "info": {"name": "ODCS 2"},
                "schema": {"fields": []},
                "extensions": {},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Aliases for tests that reference odps_contract/odcs_contract
        self.odps_contract = self.odps1
        self.odcs_contract = self.odcs1

    def test_validate_no_circular_reference_new_link(self):
        """Test that new links don't create circular references."""
        # Should not raise for new links
        validate_no_circular_reference(str(self.odps1.id), str(self.odcs1.id))

    def test_validate_no_circular_reference_direct_cycle(self):
        """Test that direct circular reference is detected."""
        # Link ODPS1 -> ODCS1
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {"odcs_link": str(self.odcs1.id)}
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {"odps_link": str(self.odps1.id)}
        self.odcs1.save()

        # Try to link ODCS1 -> ODPS1 again (would create cycle)
        with self.assertRaises(LinkingValidationError) as cm:
            validate_no_circular_reference(str(self.odps1.id), str(self.odcs1.id))

        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

    def test_validate_no_circular_reference_indirect_cycle(self):
        """Test that indirect circular reference is detected."""
        # Create chain: ODPS1 -> ODCS1 -> ODPS2 -> ODCS2
        # Then try to link ODCS2 -> ODPS1 (would create cycle)

        # Link ODPS1 -> ODCS1
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {"odcs_link": str(self.odcs1.id)}
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {"odps_link": str(self.odps1.id)}
        self.odcs1.save()

        # Link ODPS2 -> ODCS2
        self.odps2.hub_contract_json["extensions"]["x_odps"] = {"odcs_link": str(self.odcs2.id)}
        self.odps2.save()

        self.odcs2.hub_contract_json["extensions"]["x_odps"] = {"odps_link": str(self.odps2.id)}
        self.odcs2.save()

        # Link ODCS1 -> ODPS2 (creating chain)
        self.odcs1.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(self.odps2.id)
        self.odcs1.save()

        # Now try to link ODCS2 -> ODPS1 (would create cycle: ODPS1 -> ODCS1 -> ODPS2 -> ODCS2 -> ODPS1)
        with self.assertRaises(LinkingValidationError) as cm:
            validate_no_circular_reference(str(self.odps1.id), str(self.odcs2.id))

        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

    def test_validate_no_circular_reference_valid_chain(self):
        """Test that valid chains don't trigger false positives."""
        # Create valid chain: ODPS1 -> ODCS1, ODPS2 -> ODCS2 (no cycles)
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {"odcs_link": str(self.odcs1.id)}
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {"odps_link": str(self.odps1.id)}
        self.odcs1.save()

        # Should not raise for linking ODPS2 -> ODCS2 (separate chain)
        validate_no_circular_reference(str(self.odps2.id), str(self.odcs2.id))

    def test_validate_linking_with_circular_reference(self):
        """Test that re-linking already bidirectionally-linked contracts is idempotent."""
        # Link ODPS1 -> ODCS1 (bidirectional)
        self.odps1.hub_contract_json["extensions"]["x_odps"] = {"odcs_link": str(self.odcs1.id)}
        self.odps1.save()

        self.odcs1.hub_contract_json["extensions"]["x_odps"] = {"odps_link": str(self.odps1.id)}
        self.odcs1.save()

        # Re-linking already-linked contracts should be idempotent (no error)
        odps, odcs = validate_linking(
            odps_contract_id=str(self.odps1.id),
            odcs_contract_id=str(self.odcs1.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(str(odps.id), str(self.odps1.id))
        self.assertEqual(str(odcs.id), str(self.odcs1.id))

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_validate_linking_missing_odps_contract(self):
        """Test validate_linking fails when ODPS contract doesn't exist"""
        fake_odps_id = str(uuid.uuid4())

        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=fake_odps_id,
                odcs_contract_id=str(self.odcs_contract.id),
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")
        self.assertIn(fake_odps_id, cm.exception.message)

    def test_validate_linking_missing_odcs_contract(self):
        """Test validate_linking fails when ODCS contract doesn't exist"""
        fake_odcs_id = str(uuid.uuid4())

        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=str(self.odps_contract.id),
                odcs_contract_id=fake_odcs_id,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")
        self.assertIn(fake_odcs_id, cm.exception.message)

    def test_validate_linking_tenant_mismatch_odps(self):
        """Test validate_linking fails when ODPS contract belongs to different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=str(self.odps_contract.id),
                odcs_contract_id=str(self.odcs_contract.id),
                tenant_id=str(other_tenant.id),  # Different tenant
            )

        self.assertEqual(cm.exception.error_code, "TENANT_MISMATCH")

    def test_validate_linking_tenant_mismatch_odcs(self):
        """Test validate_linking fails when ODCS contract belongs to different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_odcs = Contract.objects.create(
            tenant=other_tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "other", "info": {"name": "Other"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=str(self.odps_contract.id),
                odcs_contract_id=str(other_odcs.id),
                tenant_id=str(self.tenant.id),
            )

        self.assertIn(cm.exception.error_code, ["TENANT_MISMATCH", "INCOMPATIBLE_CONTRACTS"])
        error_str = str(cm.exception.context.get("errors", [cm.exception.message])).lower()
        self.assertIn("tenant", error_str)

    def test_validate_linking_without_tenant_id(self):
        """Linking always requires tenant_id for contract lookups."""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_linking(
                odps_contract_id=str(self.odps_contract.id),
                odcs_contract_id=str(self.odcs_contract.id),
                tenant_id=None,
            )
        self.assertEqual(cm.exception.error_code, "TENANT_ID_REQUIRED")

    def test_validate_contract_exists_invalid_id_format(self):
        """Test validate_contract_exists with invalid ID format"""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists("invalid-id-format", tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")

    def test_validate_contract_exists_empty_id(self):
        """Test validate_contract_exists with empty ID"""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_exists("", tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.error_code, "CONTRACT_NOT_FOUND")

    def test_validate_contract_compatibility_same_contract(self):
        """Test validate_contract_compatibility fails when same contract used for both"""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, self.odps_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertTrue(any("ODCS" in err for err in cm.exception.context["errors"]))

    def test_validate_contract_compatibility_both_odps(self):
        """Test validate_contract_compatibility fails when both are ODPS"""
        odps2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "odps2", "info": {"name": "ODPS 2"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odps_contract, odps2)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertTrue(any("ODCS" in err for err in cm.exception.context["errors"]))

    def test_validate_contract_compatibility_both_odcs(self):
        """Test validate_contract_compatibility fails when both are ODCS"""
        odcs2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "odcs2", "info": {"name": "ODCS 2"}, "schema": {"fields": []}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(self.odcs_contract, odcs2)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        self.assertTrue(any("ODPS" in err for err in cm.exception.context["errors"]))

    def test_validate_contract_compatibility_with_warnings_normalization(self):
        """Test validate_contract_compatibility succeeds with NORMALIZED_WITH_WARNINGS"""
        self.odps_contract.normalization_status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        self.odps_contract.save()

        self.odcs_contract.normalization_status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        self.odcs_contract.save()

        # Should not raise
        validate_contract_compatibility(self.odps_contract, self.odcs_contract)

    def test_validate_no_circular_reference_same_contract(self):
        """Test validate_no_circular_reference fails when linking contract to itself"""
        with self.assertRaises(LinkingValidationError) as cm:
            validate_no_circular_reference(
                str(self.odps_contract.id),
                str(self.odps_contract.id),  # Same contract
            )

        # Should detect as circular reference (self-reference)
        self.assertEqual(cm.exception.error_code, "CIRCULAR_REFERENCE")

    def test_validate_no_circular_reference_empty_hub_contract_json(self):
        """Test validate_no_circular_reference handles empty hub_contract_json"""
        self.odps_contract.hub_contract_json = {}
        self.odps_contract.save()

        # Should not raise (no existing links)
        validate_no_circular_reference(str(self.odps_contract.id), str(self.odcs_contract.id))

    def test_validate_no_circular_reference_missing_extensions(self):
        """Test validate_no_circular_reference handles missing extensions"""
        self.odps_contract.hub_contract_json = {"id": "test", "info": {}, "schema": {}}
        self.odps_contract.save()

        # Should not raise (no existing links)
        validate_no_circular_reference(str(self.odps_contract.id), str(self.odcs_contract.id))

    def test_validate_no_circular_reference_missing_x_odps(self):
        """Test validate_no_circular_reference handles missing x_odps"""
        self.odps_contract.hub_contract_json = {
            "id": "test",
            "info": {},
            "schema": {},
            "extensions": {},
        }
        self.odps_contract.save()

        # Should not raise (no existing links)
        validate_no_circular_reference(str(self.odps_contract.id), str(self.odcs_contract.id))

    def test_validate_linking_error_context_includes_contract_ids(self):
        """Test validate_linking error context includes contract IDs"""
        fake_odps_id = str(uuid.uuid4())

        try:
            validate_linking(
                odps_contract_id=fake_odps_id,
                odcs_contract_id=str(self.odcs_contract.id),
                tenant_id=str(self.tenant.id),
            )
            self.fail("Should have raised LinkingValidationError")
        except LinkingValidationError as e:
            error_info = str(e.context) + str(e.message)
            self.assertIn(fake_odps_id, error_info)

    def test_validate_contract_compatibility_error_context_includes_all_errors(self):
        """Test validate_contract_compatibility error context includes all errors"""
        wrong_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,  # Wrong type
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json=None,  # Missing hub_contract_json
            normalization_status=NormalizationStatus.NOT_NORMALIZED,  # Not normalized
            created_by=self.user,
        )

        with self.assertRaises(LinkingValidationError) as cm:
            validate_contract_compatibility(wrong_contract, self.odcs_contract)

        self.assertEqual(cm.exception.error_code, "INCOMPATIBLE_CONTRACTS")
        # Should have multiple errors in context
        self.assertGreater(len(cm.exception.context["errors"]), 1)

    def test_validate_linking_idempotent_already_linked(self):
        """Test validate_linking is idempotent when contracts already correctly linked"""
        # Link contracts bidirectionally
        self.odps_contract.hub_contract_json["extensions"]["x_odps"] = {
            "odcs_link": str(self.odcs_contract.id)
        }
        self.odps_contract.save()

        self.odcs_contract.hub_contract_json["extensions"]["x_odps"] = {
            "odps_link": str(self.odps_contract.id)
        }
        self.odcs_contract.save()

        # Should not raise (already correctly linked)
        odps, odcs = validate_linking(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(odps.id, self.odps_contract.id)
        self.assertEqual(odcs.id, self.odcs_contract.id)
