"""
Unit tests for lineage reference resolution.

All tests use real implementations (no mocks of hub services).
Contract model uses real Contract objects in database.
"""

import uuid

from hub.apps.contracts.lineage import LineageReference
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase, ContractsTransactionTestBase
from hub.apps.tenants.models import Tenant


class TestLineageReference(ContractsTestBase):
    """Tests for LineageReference class (basic functionality, no DB)."""

    def test_lineage_reference_str(self):
        """Test string representation of lineage reference."""
        ref = LineageReference(
            namespace="ns1", name="contract1", model_name="model1", field="field1"
        )
        self.assertEqual(str(ref), "ns1/contract1/model1/field1")

    def test_lineage_reference_str_partial(self):
        """Test string representation with partial reference."""
        ref = LineageReference(namespace="ns1", name="contract1")
        self.assertEqual(str(ref), "ns1/contract1")

    def test_lineage_reference_to_dict(self):
        """Test conversion to dictionary."""
        ref = LineageReference(
            namespace="ns1", name="contract1", model_name="model1", field="field1"
        )
        result = ref.to_dict()
        self.assertEqual(result["namespace"], "ns1")
        self.assertEqual(result["name"], "contract1")
        self.assertEqual(result["model_name"], "model1")
        self.assertEqual(result["field"], "field1")

    def test_lineage_reference_to_dict_partial(self):
        """Test conversion to dictionary with partial reference."""
        ref = LineageReference(namespace="ns1", name="contract1")
        result = ref.to_dict()
        self.assertEqual(result["namespace"], "ns1")
        self.assertEqual(result["name"], "contract1")
        self.assertNotIn("model_name", result)
        self.assertNotIn("field", result)

    def test_resolve_contract_missing_namespace_or_name(self):
        """Test contract resolution when namespace or name is missing."""
        ref = LineageReference(namespace="ns1")  # Missing name
        result = ref.resolve_contract()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

        ref2 = LineageReference(name="contract1")  # Missing namespace
        result2 = ref2.resolve_contract()

        self.assertIsNone(result2)
        self.assertTrue(ref2.is_broken())


class TestLineageReferenceResolution(ContractsTransactionTestBase):
    """
    Tests for LineageReference contract resolution using real Contract model.

    Uses real Contract objects in database to verify lineage reference resolution.
    """

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Update tenant name/email for lineage tests (unique per run for --reuse-db)
        uid = uuid.uuid4().hex[:8]
        self.tenant.name = f"Lineage Test Tenant {uid}"
        self.tenant.slug = f"lineage-test-{uid}"
        self.tenant.save()

        self.user.email = f"lineage-{uid}@test.com"
        self.user.save()

        # Unique name per run so --keepdb doesn't pick up stale rows from
        # prior test executions (resolve_contract() uses .first() with no
        # ordering guarantee).
        self.contract_name = f"test-contract-{uid}"

        # Create real contract for resolution tests — the contract MUST be
        # resolvable by ``LineageReference(namespace="ns1", name=self.contract_name)``.
        # resolve_contract() filters on info.name == name AND (info.domain == namespace
        # OR extensions.namespace == namespace), so we set info.domain to match.
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": self.contract_name, "domain": "ns1"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [
                            {"name": "field1", "type": "string"},
                            {"name": "field2", "type": "integer"},
                        ],
                    },
                    {
                        "name": "model2",
                        "fields": [],
                    },
                ],
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=(
                '{"info":{"name":"'
                + self.contract_name
                + '","domain":"ns1"},'
                + '"models":[{"name":"model1","fields":'
                + '[{"name":"field1","type":"string"},{"name":"field2","type":"integer"}]},'
                + '{"name":"model2","fields":[]}]}'
            ),
            created_by=self.user,
        )

    def test_resolve_contract_success(self):
        """
        Resolve contract by namespace + name — must find the seeded contract.
        """
        ref = LineageReference(namespace="ns1", name=self.contract_name)
        result = ref.resolve_contract()

        self.assertIsNotNone(
            result,
            f"Seeded contract with info.domain='ns1' and info.name='{self.contract_name}' "
            "must be resolvable by namespace='ns1' + name='{name}'",
        )
        self.assertIsInstance(result, Contract)
        self.assertEqual(str(result.id), str(self.contract.id))
        self.assertFalse(ref.is_broken())

    def test_resolve_contract_not_found(self):
        """
        Non-existent namespace+name pair returns None and marks reference broken.
        """
        ref = LineageReference(namespace="ns1", name=f"nonexistent-{uuid.uuid4().hex[:8]}")
        result = ref.resolve_contract()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

    def test_resolve_model_success(self):
        """
        Resolve model by name — contract has ``model1``, must be found.
        """
        ref = LineageReference(namespace="ns1", name=self.contract_name, model_name="model1")
        result = ref.resolve_model()

        self.assertIsNotNone(result, "model1 must be resolvable in the seeded contract")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "model1")
        self.assertFalse(ref.is_broken())

    def test_resolve_model_not_found(self):
        """
        Test model resolution when model not found using real Contract model.

        Uses real Contract.objects.filter() to verify not found handling.
        """
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="nonexistent-model"
        )
        result = ref.resolve_model()

        self.assertIsNone(
            result, "Model 'nonexistent-model' must not be found in the seeded contract"
        )
        self.assertTrue(ref.is_broken(), "Reference must be marked broken when model is not found")

    def test_resolve_field_success(self):
        """
        Resolve field by name — model1 has field1, must be found.
        """
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="model1", field="field1"
        )
        result = ref.resolve_field()

        self.assertIsNotNone(result, "field1 must be resolvable in model1 of the seeded contract")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "field1")
        self.assertFalse(ref.is_broken())

    def test_resolve_field_not_found(self):
        """
        Test field resolution when field not found using real Contract model.

        Uses real Contract.objects.filter() to verify not found handling.
        """
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="model1", field="nonexistent-field"
        )
        result = ref.resolve_field()

        self.assertIsNone(
            result, "Field 'nonexistent-field' must not be found in model1 of the seeded contract"
        )
        self.assertTrue(ref.is_broken(), "Reference must be marked broken when field is not found")

    # Edge cases and error handling tests
    def test_lineage_reference_str_with_empty_strings(self):
        """Test string representation with empty string values.

        Empty strings are falsy in __str__, so all parts are skipped and
        the fallback ``"unknown"`` is returned.
        """
        ref = LineageReference(namespace="", name="", model_name="", field="")
        result = str(ref)
        self.assertIsInstance(result, str)
        self.assertEqual(
            result, "unknown", "All-empty-string LineageReference must repr as 'unknown'"
        )

    def test_lineage_reference_str_with_none_values(self):
        """Test string representation with None values.

        None is falsy in __str__, so all parts are skipped and the
        fallback ``"unknown"`` is returned — matching the docstring.
        """
        ref = LineageReference()
        result = str(ref)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "unknown", "All-None LineageReference must repr as 'unknown'")

    def test_lineage_reference_to_dict_with_none_values(self):
        """Test conversion to dictionary with None values.

        ``to_dict()`` only includes keys for non-None attributes, so an
        all-None LineageReference produces an empty dict.
        """
        ref = LineageReference()
        result = ref.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(
            len(result), 0, "All-None reference must produce an empty dict (no None-value keys)"
        )
        # Should not include None values
        for value in result.values():
            self.assertIsNotNone(value)

    def test_resolve_contract_with_empty_namespace_and_name(self):
        """Test contract resolution with empty namespace and name."""
        ref = LineageReference(namespace="", name="")
        result = ref.resolve_contract()
        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

    def test_resolve_contract_with_special_characters(self):
        """Contract resolution with special characters must resolve successfully."""
        # Create contracts with special characters in name/namespace so
        # the resolver actually finds them — previous version only tested
        # the "not found" branch, making the else-branch dead code.
        tenant = Tenant.objects.create(
            name=f"sc-{uuid.uuid4().hex[:8]}", slug=f"sc-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        Contract.objects.create(
            tenant=tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={
                "info": {"name": "contract.name-v2", "domain": "ns-1_test"},
                "schema": {"fields": []},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status="VALID",
        )
        ref = LineageReference(namespace="ns-1_test", name="contract.name-v2")
        result = ref.resolve_contract()
        self.assertIsNotNone(result, "Special-char reference must resolve")
        self.assertFalse(ref.is_broken(), "Resolved reference must not be marked broken")

    def test_resolve_contract_with_unicode_characters(self):
        """Contract resolution with unicode characters must resolve successfully."""
        tenant = Tenant.objects.create(
            name=f"uc-{uuid.uuid4().hex[:8]}", slug=f"uc-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        Contract.objects.create(
            tenant=tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={
                "info": {"name": "合同名称", "domain": "命名空间"},
                "schema": {"fields": []},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status="VALID",
        )
        ref = LineageReference(namespace="命名空间", name="合同名称")
        result = ref.resolve_contract()
        self.assertIsNotNone(result, "Unicode reference must resolve")
        self.assertFalse(ref.is_broken(), "Resolved reference must not be marked broken")

    def test_resolve_contract_cross_tenant_isolation(self):
        """Document tenant isolation behavior in lineage resolution.

        resolve_contract() currently queries ALL tenants (no tenant filter).
        When a contract in ``other_tenant`` matches the name+namespace,
        the resolver will find it.  This test documents the CURRENT behavior.
        A future hardening pass SHALL add a tenant filter to resolve_contract().
        """
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-ref-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        other_contract = Contract.objects.create(
            tenant=other_tenant,
            hub_contract_json={
                "info": {"name": "other-contract", "domain": "ns1"},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "other-contract", "domain": "ns1"}}',
            created_by=self.user,
        )

        ref = LineageReference(namespace="ns1", name="other-contract")
        result = ref.resolve_contract()

        # Current behavior: resolve_contract() does NOT filter by tenant,
        # so it WILL find the other_tenant's contract.
        self.assertIsNotNone(
            result,
            "Current behavior: lineage resolver finds contracts across all tenants. "
            "Tenant isolation hardening is a TODO.",
        )
        self.assertEqual(str(result.id), str(other_contract.id))

    def test_resolve_model_with_missing_contract(self):
        """Test model resolution when contract is not found."""
        ref = LineageReference(namespace="ns1", name="nonexistent", model_name="model1")
        result = ref.resolve_model()
        # Should return None if contract not found
        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

    def test_resolve_model_with_empty_models_list(self):
        """Test model resolution when contract has no models."""
        Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": "no-models-contract"},
                # No models field
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-models-contract"}}',
            created_by=self.user,
        )

        ref = LineageReference(namespace="ns1", name="no-models-contract", model_name="any-model")
        result = ref.resolve_model()
        self.assertIsNone(result, "Model must not be found when contract has no models")
        self.assertTrue(
            ref.is_broken(), "Reference must be marked broken when contract has no models"
        )

    def test_resolve_field_with_missing_model(self):
        """Test field resolution when model is not found."""
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="nonexistent-model", field="field1"
        )
        result = ref.resolve_field()
        self.assertIsNone(result, "Field must not be found when model does not exist")
        self.assertTrue(ref.is_broken(), "Reference must be marked broken when model is not found")

    def test_resolve_field_with_empty_fields_list(self):
        """Test field resolution when model has no fields."""
        Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": "no-fields-contract"},
                "models": [{"name": "empty-model", "fields": []}],  # Empty fields list
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-fields-contract"}}',
            created_by=self.user,
        )

        ref = LineageReference(
            namespace="ns1", name="no-fields-contract", model_name="empty-model", field="any-field"
        )
        result = ref.resolve_field()
        self.assertIsNone(result, "Field must not be found when model has empty fields list")
        self.assertTrue(ref.is_broken(), "Reference must be marked broken when model has no fields")

    def test_is_broken_with_unresolved_reference(self):
        """Test is_broken() with unresolved reference."""
        ref = LineageReference(namespace="ns1", name="nonexistent")
        # Initially broken state is None
        # After attempting resolution, should be True
        ref.resolve_contract()
        self.assertTrue(ref.is_broken())

    def test_is_broken_with_resolved_reference(self):
        """is_broken() returns False for a successfully resolved reference."""
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="model1", field="field1"
        )
        ref.resolve_field()
        self.assertFalse(
            ref.is_broken(), "field1 in model1 of the seeded contract must resolve → not broken"
        )

    def test_resolve_contract_caching_behavior(self):
        """Contract resolution must use instance-level caching for repeated calls."""
        ref = LineageReference(namespace="ns1", name=self.contract_name)
        result1 = ref.resolve_contract()
        result2 = ref.resolve_contract()

        self.assertIsNotNone(result1)
        # Same Python object — cached on instance.
        self.assertIs(
            result1,
            result2,
            "Second resolve_contract() must return the same cached Contract instance",
        )

    def test_resolve_model_caching_behavior(self):
        """Model resolution must use cached contract — instance-level caching."""
        ref = LineageReference(namespace="ns1", name=self.contract_name, model_name="model1")
        result1 = ref.resolve_model()
        result2 = ref.resolve_model()

        self.assertIsNotNone(result1)
        self.assertEqual(result1["name"], "model1")
        # Same dict identity — cached on instance.
        self.assertIs(result1, result2)

    def test_resolve_field_caching_behavior(self):
        """Field resolution must use cached contract + model — instance-level caching."""
        ref = LineageReference(
            namespace="ns1", name=self.contract_name, model_name="model1", field="field1"
        )
        result1 = ref.resolve_field()
        result2 = ref.resolve_field()

        self.assertIsNotNone(result1)
        self.assertEqual(result1["name"], "field1")
        self.assertIs(result1, result2)

    def test_resolve_contract_self_reference(self):
        """Contract resolution handles a contract that references itself.

        A contract whose ``lineage.contracts`` lists its own name/namespace
        must resolve to itself — not be marked broken.
        """
        uid = uuid.uuid4().hex[:8]
        self_ref_name = f"self-ref-{uid}"

        contract = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": self_ref_name, "domain": "ns1"},
                "lineage": {"contracts": [{"namespace": "ns1", "name": self_ref_name}]},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw=f'{{"info":{{"name":"{self_ref_name}","domain":"ns1"}}}}',
            created_by=self.user,
        )

        ref = LineageReference(namespace="ns1", name=self_ref_name)
        result = ref.resolve_contract()

        self.assertIsNotNone(result, "Self-referencing contract must resolve to itself")
        self.assertEqual(
            str(result.id),
            str(contract.id),
            "Self-reference must return the same contract instance",
        )
        self.assertFalse(ref.is_broken(), "Self-reference must not be marked broken")

    def test_resolve_contract_circular_reference(self):
        """Two contracts that reference each other both resolve correctly.

        Contract A → lineage.contracts = [B], Contract B → lineage.contracts = [A].
        Both must be resolvable — circular lineage is a graph property, not a
        resolution failure.
        """
        uid = uuid.uuid4().hex[:8]
        name_a = f"circ-a-{uid}"
        name_b = f"circ-b-{uid}"

        contract_b = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": name_b, "domain": "ns1"},
                "lineage": {"contracts": [{"namespace": "ns1", "name": name_a}]},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw=f'{{"info":{{"name":"{name_b}","domain":"ns1"}}}}',
            created_by=self.user,
        )
        contract_a = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={
                "info": {"name": name_a, "domain": "ns1"},
                "lineage": {"contracts": [{"namespace": "ns1", "name": name_b}]},
            },
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw=f'{{"info":{{"name":"{name_a}","domain":"ns1"}}}}',
            created_by=self.user,
        )

        ref_a = LineageReference(namespace="ns1", name=name_a)
        ref_b = LineageReference(namespace="ns1", name=name_b)

        result_a = ref_a.resolve_contract()
        result_b = ref_b.resolve_contract()

        self.assertIsNotNone(result_a, "Contract A must resolve in a circular reference pair")
        self.assertEqual(str(result_a.id), str(contract_a.id))
        self.assertFalse(ref_a.is_broken())

        self.assertIsNotNone(result_b, "Contract B must resolve in a circular reference pair")
        self.assertEqual(str(result_b.id), str(contract_b.id))
        self.assertFalse(ref_b.is_broken())

    def test_lineage_reference_with_very_long_names(self):
        """Test lineage reference with very long namespace/name values."""
        long_name = "a" * 1000
        ref = LineageReference(namespace=long_name, name=long_name)
        result = str(ref)
        # Should handle long names without error
        self.assertIsInstance(result, str)
        self.assertIn(long_name, result)
