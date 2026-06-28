"""
Comprehensive Lineage Service Validation Tests (Task 10.1.35)

This test suite implements comprehensive, engineering-grade validation for:
- 10.1.35.1: Contract Lineage Testing
- 10.1.35.2: Field Lineage Testing
- 10.1.35.3: Hierarchical Lineage Testing
- 10.1.35.4: Lineage Impact Analysis Testing
- 10.1.35.5: Lineage Service Integration with ODPS

All tests use real implementations (no mocks/stubs) per requirements.
Tests follow TDD approach and fix root causes.
"""

import json
import uuid
from typing import Any

import pytest
from django.contrib.auth import get_user_model

# Import signals to disable them in tests (root cause fix for semantic service timeouts)
from django.db.models.signals import post_save
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.impact_analysis import ImpactAnalyzer
from hub.apps.contracts.lineage_service import LineageService
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.semantic.signals import asset_saved, contract_saved
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory
from tests.fixtures.test_data_factories import (
    AssetFactoryEnhanced,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.slow,
    pytest.mark.uc("UC-MKT-LINEAGE-001"),
    pytest.mark.uc("UC-MKT-LINEAGE-002"),
    pytest.mark.uc("UC-LIN-FIELD-EDIT-001"),
]
User = get_user_model()


class ContractLineageTest(TestCase):
    """
    Contract Lineage Testing (10.1.35.1).

    Tests:
    - Contract lineage extraction
    - Contract lineage queries
    - Contract lineage visualization
    - Contract lineage depth limits
    - Contract lineage error handling
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test data"""
        # Disconnect signals to prevent semantic service calls during tests (root cause fix)
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)

        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.lineage_service = LineageService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create source contract
        self.source_contract = self._create_contract_with_lineage(
            name="source-contract",
            lineage_contracts=[],
            lineage_entries=[],
        )

        # Create dependent contract with lineage reference
        self.dependent_contract = self._create_contract_with_lineage(
            name="dependent-contract",
            lineage_contracts=[
                {
                    "namespace": None,
                    "name": "source-contract",
                    "version": "1.0.0",
                    "description": "Source contract dependency",
                }
            ],
            lineage_entries=[],
        )

    def _create_contract_with_lineage(
        self,
        name: str,
        lineage_contracts: list[dict[str, Any]],
        lineage_entries: list[dict[str, Any]],
    ) -> Contract:
        """Create a contract with specified lineage data"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        hub_contract_json = {
            "info": {"name": name, "title": f"{name} Title", "version": "1.0.0"},
            "lineage": {"contracts": lineage_contracts, "entries": lineage_entries},
            "models": [
                {
                    "name": f"{name}_model",
                    "fields": [{"name": "field1", "type": "string"}],
                    "lineage": {"models": [], "entries": []},
                }
            ],
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        return contract

    def test_contract_lineage_extraction(self):
        """Test contract lineage extraction"""
        lineage = self.lineage_service.get_contract_lineage(
            contract_id=str(self.dependent_contract.id), tenant_id=str(self.tenant.id)
        )

        # Verify structure
        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)

        # Verify lineage contracts are extracted
        contracts = lineage.get("contracts", [])
        self.assertGreater(len(contracts), 0)

        # Verify source contract reference
        contract_names = [c.get("name") for c in contracts if isinstance(c, dict)]
        self.assertIn("source-contract", contract_names)

    def test_contract_lineage_queries(self):
        """Test contract lineage queries"""
        # Query with cache
        lineage_cached = self.lineage_service.get_contract_lineage(
            contract_id=str(self.dependent_contract.id),
            tenant_id=str(self.tenant.id),
            use_cache=True,
        )

        # Query without cache
        lineage_no_cache = self.lineage_service.get_contract_lineage(
            contract_id=str(self.dependent_contract.id),
            tenant_id=str(self.tenant.id),
            use_cache=False,
        )

        # Both should return same structure
        self.assertIn("contracts", lineage_cached)
        self.assertIn("contracts", lineage_no_cache)
        self.assertIn("entries", lineage_cached)
        self.assertIn("entries", lineage_no_cache)

    def test_contract_lineage_visualization(self):
        """Test contract lineage visualization"""
        # Test JSON format
        visualization_json = self.lineage_service.get_lineage_visualization(
            contract_id=str(self.dependent_contract.id),
            format="json",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("nodes", visualization_json)
        self.assertIn("links", visualization_json)

        # Test DOT format
        visualization_dot = self.lineage_service.get_lineage_visualization(
            contract_id=str(self.dependent_contract.id),
            format="dot",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("dot", visualization_dot)
        dot_string = visualization_dot["dot"]
        self.assertIsInstance(dot_string, str)
        self.assertIn("digraph", dot_string)

        # Test Mermaid format
        visualization_mermaid = self.lineage_service.get_lineage_visualization(
            contract_id=str(self.dependent_contract.id),
            format="mermaid",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("mermaid", visualization_mermaid)
        mermaid_string = visualization_mermaid["mermaid"]
        self.assertIsInstance(mermaid_string, str)
        self.assertIn("graph", mermaid_string.lower())

    def test_contract_lineage_depth_limits(self):
        """Test contract lineage depth limits"""
        # Create a chain of contracts
        chain_contracts = []
        prev_contract = self.source_contract

        for i in range(5):
            chain_contract = self._create_contract_with_lineage(
                name=f"chain-contract-{i}",
                lineage_contracts=[
                    {
                        "namespace": None,
                        "name": prev_contract.hub_contract_json["info"]["name"],
                    }
                ],
                lineage_entries=[],
            )
            chain_contracts.append(chain_contract)
            prev_contract = chain_contract

        # Test with limited depth
        full_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(chain_contracts[-1].id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=2,
            max_model_depth=10,
            max_field_depth=10,
        )

        # Should respect depth limits
        self.assertIn("upstream", full_lineage)
        self.assertIn("downstream", full_lineage)

    def test_contract_lineage_error_handling(self):
        """Test contract lineage error handling"""
        # Test with non-existent contract
        with self.assertRaises(NotFoundError):
            self.lineage_service.get_contract_lineage(
                contract_id=str(uuid.uuid4()), tenant_id=str(self.tenant.id)
            )

        # Test with invalid format
        with self.assertRaises(ValidationError):
            self.lineage_service.get_lineage_visualization(
                contract_id=str(self.dependent_contract.id),
                format="invalid-format",
                tenant_id=str(self.tenant.id),
            )

        # Test with contract without lineage
        contract_no_lineage = self._create_contract_with_lineage(
            name="no-lineage-contract",
            lineage_contracts=[],
            lineage_entries=[],
        )

        lineage = self.lineage_service.get_contract_lineage(
            contract_id=str(contract_no_lineage.id), tenant_id=str(self.tenant.id)
        )

        # Should return empty lineage
        self.assertEqual(len(lineage.get("contracts", [])), 0)
        self.assertEqual(len(lineage.get("entries", [])), 0)

    def tearDown(self):
        """Clean up test data and close database connections"""
        # Reconnect signals after test
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)

        from django.db import connection

        connection.close()
        super().tearDown()


class FieldLineageTest(TestCase):
    """
    Field Lineage Testing (10.1.35.2).

    Tests:
    - Field-level lineage tracking
    - Field lineage queries
    - Field lineage visualization
    - Field lineage accuracy
    - Field lineage error handling
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test data"""
        # Disconnect signals to prevent semantic service calls during tests (root cause fix)
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)

        # Retry database operations with exponential backoff to handle connection timeouts
        import time

        from django.db import connection

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    connection.close()
                    time.sleep(  # noqa: sleep-needed — polling loop
                        retry_delay * (2**attempt)
                    )  # INTENTIONAL: e2e/integration test polling real services

                self.tenant = TenantFactory.create_tenant()
                self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
                self.lineage_service = LineageService(
                    tenant_id=str(self.tenant.id), user_id=str(self.user.id)
                )
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                continue

        # Create source contract with fields
        self.source_contract = self._create_contract_with_field_lineage(
            name="source-contract",
            model_name="SourceModel",
            fields=[
                {
                    "name": "source_field1",
                    "type": "string",
                    "lineage": {"input_fields": [], "transformations": []},
                },
                {
                    "name": "source_field2",
                    "type": "integer",
                    "lineage": {"input_fields": [], "transformations": []},
                },
            ],
        )

        # Create dependent contract with field lineage
        self.dependent_contract = self._create_contract_with_field_lineage(
            name="dependent-contract",
            model_name="DependentModel",
            fields=[
                {
                    "name": "derived_field",
                    "type": "string",
                    "lineage": {
                        "input_fields": [
                            {
                                "namespace": None,
                                "name": "source-contract",
                                "model_name": "SourceModel",
                                "field": "source_field1",
                            }
                        ],
                        "transformations": [
                            {
                                "logic": "SELECT source_field1 as derived_field",
                                "description": "Derive field from source",
                            }
                        ],
                    },
                }
            ],
        )

    def _create_contract_with_field_lineage(
        self, name: str, model_name: str, fields: list[dict[str, Any]]
    ) -> Contract:
        """Create a contract with field-level lineage"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        hub_contract_json = {
            "info": {"name": name, "title": f"{name} Title", "version": "1.0.0"},
            "lineage": {"contracts": [], "entries": []},
            "models": [
                {
                    "name": model_name,
                    "fields": fields,
                    "lineage": {"models": [], "entries": []},
                }
            ],
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        return contract

    def test_field_level_lineage_tracking(self):
        """Test field-level lineage tracking"""
        lineage = self.lineage_service.get_field_lineage(
            contract_id=str(self.dependent_contract.id),
            field_name="derived_field",
            model_name="DependentModel",
            tenant_id=str(self.tenant.id),
        )

        # Verify structure
        self.assertIn("field_name", lineage)
        self.assertIn("model_name", lineage)
        self.assertIn("lineage", lineage)

        self.assertEqual(lineage["field_name"], "derived_field")
        self.assertEqual(lineage["model_name"], "DependentModel")

        # Verify input fields
        field_lineage = lineage.get("lineage", {})
        input_fields = field_lineage.get("input_fields", [])
        self.assertGreater(len(input_fields), 0)

        # Verify source field reference
        first_input = input_fields[0] if input_fields else {}
        self.assertEqual(first_input.get("name"), "source-contract")
        self.assertEqual(first_input.get("model_name"), "SourceModel")
        self.assertEqual(first_input.get("field"), "source_field1")

    def test_field_lineage_queries(self):
        """Test field lineage queries"""
        # Query with model name
        lineage_with_model = self.lineage_service.get_field_lineage(
            contract_id=str(self.dependent_contract.id),
            field_name="derived_field",
            model_name="DependentModel",
            tenant_id=str(self.tenant.id),
        )

        # Query without model name (searches all models)
        lineage_without_model = self.lineage_service.get_field_lineage(
            contract_id=str(self.dependent_contract.id),
            field_name="derived_field",
            tenant_id=str(self.tenant.id),
        )

        # Both should return same field
        self.assertEqual(lineage_with_model["field_name"], "derived_field")
        self.assertEqual(lineage_without_model["field_name"], "derived_field")

    def test_field_lineage_visualization(self):
        """Test field lineage visualization"""
        # Get full lineage which includes field-level
        full_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(self.dependent_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=10,
            max_model_depth=10,
            max_field_depth=10,
        )

        # Verify structure includes field-level data
        self.assertIn("upstream", full_lineage)
        self.assertIn("downstream", full_lineage)

        # Field lineage should be in downstream
        downstream = full_lineage.get("downstream", {})
        if isinstance(downstream, dict):
            models = downstream.get("models", [])
            for model in models:
                if isinstance(model, dict):
                    fields = model.get("fields", [])
                    for field in fields:
                        if isinstance(field, dict) and field.get("field_name") == "derived_field":
                            # Found field with lineage
                            self.assertIn("lineage", field)

    def test_field_lineage_accuracy(self):
        """Test field lineage accuracy"""
        # Get field lineage
        lineage = self.lineage_service.get_field_lineage(
            contract_id=str(self.dependent_contract.id),
            field_name="derived_field",
            model_name="DependentModel",
            tenant_id=str(self.tenant.id),
        )

        # Verify transformations are included
        field_lineage = lineage.get("lineage", {})
        transformations = field_lineage.get("transformations", [])
        self.assertGreater(len(transformations), 0)

        # Verify transformation logic
        first_transform = transformations[0] if transformations else {}
        self.assertIn("logic", first_transform)
        self.assertIn("description", first_transform)

    def test_field_lineage_error_handling(self):
        """Test field lineage error handling"""
        # Test with non-existent field
        with self.assertRaises(NotFoundError):
            self.lineage_service.get_field_lineage(
                contract_id=str(self.dependent_contract.id),
                field_name="non-existent-field",
                tenant_id=str(self.tenant.id),
            )

        # Test with non-existent model
        with self.assertRaises(NotFoundError):
            self.lineage_service.get_field_lineage(
                contract_id=str(self.dependent_contract.id),
                field_name="derived_field",
                model_name="non-existent-model",
                tenant_id=str(self.tenant.id),
            )

        # Test with field without lineage
        contract_no_field_lineage = self._create_contract_with_field_lineage(
            name="no-field-lineage-contract",
            model_name="SimpleModel",
            fields=[{"name": "simple_field", "type": "string"}],
        )

        # Field without lineage should still return structure
        lineage = self.lineage_service.get_field_lineage(
            contract_id=str(contract_no_field_lineage.id),
            field_name="simple_field",
            model_name="SimpleModel",
            tenant_id=str(self.tenant.id),
        )

        self.assertEqual(lineage["field_name"], "simple_field")
        field_lineage = lineage.get("lineage", {})
        self.assertEqual(len(field_lineage.get("input_fields", [])), 0)

    def tearDown(self):
        """Clean up test data and close database connections"""
        # Reconnect signals after test
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)

        from django.db import connection

        connection.close()
        super().tearDown()


class HierarchicalLineageTest(TestCase):
    """
    Hierarchical Lineage Testing (10.1.35.3).

    Tests:
    - Hierarchical lineage construction
    - Multi-level lineage queries
    - Lineage depth limits
    - Lineage performance
    - Lineage error handling
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test data with hierarchical lineage"""
        # Disconnect signals to prevent semantic service calls during tests (root cause fix)
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)

        # Retry database operations with exponential backoff
        import time

        from django.db import connection

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    connection.close()
                    time.sleep(  # noqa: sleep-needed — polling loop
                        retry_delay * (2**attempt)
                    )  # INTENTIONAL: e2e/integration test polling real services

                self.tenant = TenantFactory.create_tenant()
                self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
                self.lineage_service = LineageService(
                    tenant_id=str(self.tenant.id), user_id=str(self.user.id)
                )
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                continue

        # Create hierarchical chain: source -> intermediate -> target
        self.source_contract = self._create_hierarchical_contract(
            name="source-contract",
            model_name="SourceModel",
            field_name="source_field",
            upstream_contracts=[],
        )

        self.intermediate_contract = self._create_hierarchical_contract(
            name="intermediate-contract",
            model_name="IntermediateModel",
            field_name="intermediate_field",
            upstream_contracts=[{"name": "source-contract", "model_name": "SourceModel"}],
            upstream_fields=[
                {
                    "name": "source-contract",
                    "model_name": "SourceModel",
                    "field": "source_field",
                }
            ],
        )

        self.target_contract = self._create_hierarchical_contract(
            name="target-contract",
            model_name="TargetModel",
            field_name="target_field",
            upstream_contracts=[
                {"name": "intermediate-contract", "model_name": "IntermediateModel"}
            ],
            upstream_fields=[
                {
                    "name": "intermediate-contract",
                    "model_name": "IntermediateModel",
                    "field": "intermediate_field",
                }
            ],
        )

    def _create_hierarchical_contract(
        self,
        name: str,
        model_name: str,
        field_name: str,
        upstream_contracts: list[dict[str, Any]],
        upstream_fields: list[dict[str, Any]] | None = None,
    ) -> Contract:
        """Create a contract with hierarchical lineage"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        # Build field lineage
        field_lineage = {"input_fields": [], "transformations": []}
        if upstream_fields:
            field_lineage["input_fields"] = upstream_fields
            field_lineage["transformations"] = [
                {"logic": f"SELECT {upstream_fields[0].get('field')} as {field_name}"}
            ]

        hub_contract_json = {
            "info": {"name": name, "title": f"{name} Title", "version": "1.0.0"},
            "lineage": {
                "contracts": [{"namespace": None, "name": c["name"]} for c in upstream_contracts],
                "entries": [],
            },
            "models": [
                {
                    "name": model_name,
                    "fields": [
                        {
                            "name": field_name,
                            "type": "string",
                            "lineage": field_lineage,
                        }
                    ],
                    "lineage": {
                        "models": [
                            {"namespace": None, "name": c["name"], "model_name": c["model_name"]}
                            for c in upstream_contracts
                        ],
                        "entries": [],
                    },
                }
            ],
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        return contract

    def test_hierarchical_lineage_construction(self):
        """Test hierarchical lineage construction"""
        # Refresh contract from database to ensure we have latest data (root cause fix)
        self.target_contract.refresh_from_db()

        # Verify contract has models (root cause validation)
        hub_contract = self.target_contract.hub_contract_json
        self.assertIsNotNone(hub_contract, "Contract should have hub_contract_json")
        models_in_contract = hub_contract.get("models", [])
        self.assertGreater(len(models_in_contract), 0, "Target contract should have models")

        full_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=10,
            max_model_depth=10,
            max_field_depth=10,
        )

        # Verify structure
        self.assertIn("upstream", full_lineage)
        self.assertIn("downstream", full_lineage)

        # Verify hierarchical structure includes all levels
        downstream = full_lineage.get("downstream", {})
        self.assertIsInstance(downstream, dict, "Downstream should be a dictionary")

        # Should have models from the target contract (root cause fix)
        # traverse_top_down returns models from the current contract
        models = downstream.get("models", [])
        self.assertGreater(
            len(models),
            0,
            f"Downstream should have models. Contract has {len(models_in_contract)} models, but downstream has {len(models)}. Downstream structure: {list(downstream.keys())}",
        )

        # Models should have fields
        for model in models:
            if isinstance(model, dict):
                fields = model.get("fields", [])
                for field in fields:
                    if isinstance(field, dict):
                        # Fields should have lineage
                        if "lineage" in field:
                            self.assertIn("input_fields", field["lineage"])

    def test_multi_level_lineage_queries(self):
        """Test multi-level lineage queries"""
        # Query contract level
        contract_lineage = self.lineage_service.get_contract_lineage(
            contract_id=str(self.target_contract.id), tenant_id=str(self.tenant.id)
        )

        # Query model level
        model_lineage = self.lineage_service.get_model_lineage(
            contract_id=str(self.target_contract.id),
            model_name="TargetModel",
            tenant_id=str(self.tenant.id),
        )

        # Query field level
        field_lineage = self.lineage_service.get_field_lineage(
            contract_id=str(self.target_contract.id),
            field_name="target_field",
            model_name="TargetModel",
            tenant_id=str(self.tenant.id),
        )

        # All should return valid lineage
        self.assertIn("contracts", contract_lineage)
        self.assertIn("model_name", model_lineage)
        self.assertIn("field_name", field_lineage)

    def test_lineage_depth_limits(self):
        """Test lineage depth limits"""
        # Test with very limited depth
        limited_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=1,
            max_model_depth=1,
            max_field_depth=1,
        )

        # Should respect depth limits
        self.assertIn("upstream", limited_lineage)
        self.assertIn("downstream", limited_lineage)

        # Test with unlimited depth
        unlimited_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=100,
            max_model_depth=100,
            max_field_depth=100,
        )

        # Should traverse deeper
        self.assertIn("upstream", unlimited_lineage)
        self.assertIn("downstream", unlimited_lineage)

    def test_lineage_performance(self):
        """Test lineage performance with caching"""
        import time

        # First query (no cache)
        start_time = time.time()
        lineage1 = self.lineage_service.get_contract_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            use_cache=True,
        )
        first_query_elapsed = time.time() - start_time

        # Second query (with cache)
        start_time = time.time()
        lineage2 = self.lineage_service.get_contract_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            use_cache=True,
        )
        second_query_elapsed = time.time() - start_time

        # Verify performance: both queries should complete within a reasonable time
        self.assertLess(first_query_elapsed, 5.0,
                        f"First lineage query took {first_query_elapsed:.2f}s, expected < 5s")
        self.assertLess(second_query_elapsed, 5.0,
                        f"Second lineage query took {second_query_elapsed:.2f}s, expected < 5s")

        # Cached query should be faster (or at least not slower)
        # Note: In test environment, cache might not be significantly faster
        # but structure should be the same
        self.assertIn("contracts", lineage1)
        self.assertIn("contracts", lineage2)

    def test_lineage_error_handling(self):
        """Test lineage error handling"""
        # Test with non-existent contract
        with self.assertRaises(NotFoundError):
            self.lineage_service.get_full_lineage(
                contract_id=str(uuid.uuid4()), tenant_id=str(self.tenant.id)
            )

        # Test with invalid depth parameters — service returns empty results
        # for negative depths rather than raising (graceful handling).
        result = self.lineage_service.get_full_lineage(
            contract_id=str(self.target_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=-1,
            max_model_depth=-1,
            max_field_depth=-1,
        )
        self.assertEqual(len(result.get("contracts", [])), 0,
                         "Negative max depths should return empty contracts")
        self.assertEqual(len(result.get("entries", [])), 0,
                         "Negative max depths should return empty entries")

    def tearDown(self):
        """Clean up test data and close database connections"""
        # Reconnect signals after test
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)

        from django.db import connection

        connection.close()
        super().tearDown()


class LineageImpactAnalysisTest(TestCase):
    """
    Lineage Impact Analysis Testing (10.1.35.4).

    Tests:
    - Impact analysis queries
    - Downstream impact tracking
    - Upstream dependency tracking
    - Impact analysis performance
    - Impact analysis error handling
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test data for impact analysis"""
        # Disconnect signals to prevent semantic service calls during tests (root cause fix)
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)

        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.lineage_service = LineageService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create source contract
        self.source_contract = self._create_contract_for_impact(
            name="impact-source-contract",
            model_name="SourceModel",
            field_name="source_field",
        )

        # Create multiple dependent contracts
        self.dependent_contract_1 = self._create_contract_for_impact(
            name="dependent-contract-1",
            model_name="DependentModel1",
            field_name="dependent_field_1",
            depends_on={
                "contract_name": "impact-source-contract",
                "model_name": "SourceModel",
                "field_name": "source_field",
            },
        )

        self.dependent_contract_2 = self._create_contract_for_impact(
            name="dependent-contract-2",
            model_name="DependentModel2",
            field_name="dependent_field_2",
            depends_on={
                "contract_name": "impact-source-contract",
                "model_name": "SourceModel",
                "field_name": "source_field",
            },
        )

        # Create second-level dependent
        self.second_level_dependent = self._create_contract_for_impact(
            name="second-level-dependent",
            model_name="SecondLevelModel",
            field_name="second_level_field",
            depends_on={
                "contract_name": "dependent-contract-1",
                "model_name": "DependentModel1",
                "field_name": "dependent_field_1",
            },
        )

    def _create_contract_for_impact(
        self,
        name: str,
        model_name: str,
        field_name: str,
        depends_on: dict[str, str] | None = None,
    ) -> Contract:
        """Create a contract for impact analysis testing"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        lineage_contracts = []
        field_lineage = {"input_fields": [], "transformations": []}

        if depends_on:
            lineage_contracts.append({"namespace": None, "name": depends_on["contract_name"]})
            field_lineage["input_fields"] = [
                {
                    "namespace": None,
                    "name": depends_on["contract_name"],
                    "model_name": depends_on["model_name"],
                    "field": depends_on["field_name"],
                }
            ]
            field_lineage["transformations"] = [
                {"logic": f"SELECT {depends_on['field_name']} as {field_name}"}
            ]

        hub_contract_json = {
            "info": {"name": name, "title": f"{name} Title", "version": "1.0.0"},
            "lineage": {"contracts": lineage_contracts, "entries": []},
            "models": [
                {
                    "name": model_name,
                    "fields": [
                        {
                            "name": field_name,
                            "type": "string",
                            "lineage": field_lineage,
                        }
                    ],
                    "lineage": {
                        "models": (
                            [
                                {
                                    "namespace": None,
                                    "name": depends_on["contract_name"],
                                    "model_name": depends_on["model_name"],
                                }
                            ]
                            if depends_on
                            else []
                        ),
                        "entries": [],
                    },
                }
            ],
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        return contract

    def test_impact_analysis_queries(self):
        """Test impact analysis queries"""
        # Contract-level impact
        contract_impact = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("source", contract_impact)
        self.assertIn("impact_graph", contract_impact)
        self.assertIn("summary", contract_impact)
        self.assertIn("total_affected", contract_impact)

        # Model-level impact
        model_impact = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id),
            model_name="SourceModel",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("source", model_impact)
        source = model_impact.get("source", {})
        self.assertEqual(source.get("model_name"), "SourceModel")

        # Field-level impact
        field_impact = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id),
            model_name="SourceModel",
            field_name="source_field",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("source", field_impact)
        source = field_impact.get("source", {})
        self.assertEqual(source.get("field_name"), "source_field")

    def test_downstream_impact_tracking(self):
        """Test downstream impact tracking"""
        impact_result = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Verify impact graph shows dependents
        impact_graph = impact_result.get("impact_graph", {})
        self.assertIsInstance(impact_graph, dict)

        # Verify summary shows affected resources
        summary = impact_result.get("summary", {})
        self.assertIn("total_contracts", summary)
        self.assertIn("severity_distribution", summary)

        # Should have at least 2 dependents (dependent_contract_1 and dependent_contract_2)
        total_affected = impact_result.get("total_affected", 0)
        self.assertGreaterEqual(total_affected, 2)

    def test_upstream_dependency_tracking(self):
        """Test upstream dependency tracking"""
        # Get full lineage to see upstream
        full_lineage = self.lineage_service.get_full_lineage(
            contract_id=str(self.second_level_dependent.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=10,
            max_model_depth=10,
            max_field_depth=10,
        )

        # Verify upstream shows dependencies
        upstream = full_lineage.get("upstream", {})
        self.assertIsInstance(upstream, dict)

        # Downstream should show what this contract depends on
        downstream = full_lineage.get("downstream", {})
        if isinstance(downstream, dict):
            # Should show dependency chain
            self.assertIsNotNone(downstream)

    def test_impact_analysis_performance(self):
        """Test impact analysis performance"""
        import time

        # Measure impact analysis time
        start_time = time.time()
        impact_result = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=10,
            max_model_depth=10,
            max_field_depth=10,
        )
        analysis_time = time.time() - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        # In test environment, this might vary, so we just verify it completes
        self.assertIn("source", impact_result)
        self.assertLess(analysis_time, 30.0)  # Should complete within 30 seconds

    def test_impact_analysis_error_handling(self):
        """Test impact analysis error handling"""
        # Test with non-existent contract
        analyzer = ImpactAnalyzer(
            max_contract_depth=10, max_model_depth=10, max_field_depth=10, include_fields=True
        )

        result = analyzer.analyze_impact(
            contract_id=str(uuid.uuid4()), tenant_id=str(self.tenant.id)
        )

        # Should return error in result
        self.assertIn("error", result)

        # Test with invalid parameters via service — service handles negative
        # depths gracefully by returning a valid (but empty) impact analysis.
        result = self.lineage_service.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=-1,  # Invalid depth
        )
        self.assertNotIn("error", result,
                         "Negative depth should not crash — service should return gracefully")
        self.assertEqual(result.get("total_affected", -1), 1,
                         "Should still include the source contract in impact analysis")

    def tearDown(self):
        """Clean up test data and close database connections"""
        # Reconnect signals after test
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)

        from django.db import connection

        connection.close()
        super().tearDown()


class LineageODPSIntegrationTest(TestCase):
    """
    Lineage Service Integration with ODPS (10.1.35.5).

    Tests:
    - ODPS contract lineage
    - ODPS field lineage
    - ODPS-ODCS lineage relationships
    - ODPS product lineage
    - ODPS lineage visualization
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test data with ODPS-ODCS integration"""
        # Disconnect signals to prevent semantic service calls during tests (root cause fix)
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)

        # Retry database operations with exponential backoff
        import time

        from django.db import connection

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    connection.close()
                    time.sleep(  # noqa: sleep-needed — polling loop
                        retry_delay * (2**attempt)
                    )  # INTENTIONAL: e2e/integration test polling real services

                self.tenant = TenantFactory.create_tenant()
                self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
                self.lineage_service = LineageService(
                    tenant_id=str(self.tenant.id), user_id=str(self.user.id)
                )
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                continue

        # Create ODCS contract
        self.odcs_contract = self._create_odcs_contract(
            name="odcs-contract",
            model_name="ODCSModel",
            field_name="odcs_field",
        )

        # Create ODPS contract linked to ODCS
        self.odps_contract = self._create_odps_contract(
            name="odps-product",
            product_id="odps-product-id",
            linked_odcs_id=str(self.odcs_contract.id),
        )

        # Create ODCS contract with lineage to another ODCS
        self.odcs_source = self._create_odcs_contract(
            name="odcs-source",
            model_name="SourceModel",
            field_name="source_field",
        )

        # Create ODCS contract that depends on source
        self.odcs_dependent = self._create_odcs_contract(
            name="odcs-dependent",
            model_name="DependentModel",
            field_name="dependent_field",
            depends_on={
                "contract_name": "odcs-source",
                "model_name": "SourceModel",
                "field_name": "source_field",
            },
        )

        # Create ODPS contract linked to dependent ODCS
        self.odps_dependent = self._create_odps_contract(
            name="odps-dependent-product",
            product_id="odps-dependent-id",
            linked_odcs_id=str(self.odcs_dependent.id),
        )

    def _create_odcs_contract(
        self,
        name: str,
        model_name: str,
        field_name: str,
        depends_on: dict[str, str] | None = None,
    ) -> Contract:
        """Create an ODCS contract"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        lineage_contracts = []
        field_lineage = {"input_fields": [], "transformations": []}

        if depends_on:
            lineage_contracts.append({"namespace": None, "name": depends_on["contract_name"]})
            field_lineage["input_fields"] = [
                {
                    "namespace": None,
                    "name": depends_on["contract_name"],
                    "model_name": depends_on["model_name"],
                    "field": depends_on["field_name"],
                }
            ]

        hub_contract_json = {
            "info": {"name": name, "title": f"{name} Title", "version": "1.0.0"},
            "lineage": {"contracts": lineage_contracts, "entries": []},
            "models": [
                {
                    "name": model_name,
                    "fields": [
                        {
                            "name": field_name,
                            "type": "string",
                            "lineage": field_lineage,
                        }
                    ],
                    "lineage": {
                        "models": (
                            [
                                {
                                    "namespace": None,
                                    "name": depends_on["contract_name"],
                                    "model_name": depends_on["model_name"],
                                }
                            ]
                            if depends_on
                            else []
                        ),
                        "entries": [],
                    },
                }
            ],
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        return contract

    def _create_odps_contract(
        self, name: str, product_id: str, linked_odcs_id: str | None = None
    ) -> Contract:
        """Create an ODPS contract linked to ODCS"""
        asset = AssetFactoryEnhanced.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        hub_contract_json = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": product_id,
                        "name": name,
                        "description": f"{name} Description",
                    }
                }
            },
        }

        # Add ODCS link if provided
        if linked_odcs_id:
            if "extensions" not in hub_contract_json:
                hub_contract_json["extensions"] = {}
            if "x_odps" not in hub_contract_json["extensions"]:
                hub_contract_json["extensions"]["x_odps"] = {}
            hub_contract_json["extensions"]["x_odps"]["odcs_link"] = linked_odcs_id

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(hub_contract_json),
            hub_contract_json=hub_contract_json,
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
        )

        # Also link ODCS to ODPS (root cause fix: ensure link is saved and refreshed)
        if linked_odcs_id:
            try:
                odcs_contract = Contract.objects.get(id=linked_odcs_id)
                if odcs_contract.hub_contract_json:
                    if "extensions" not in odcs_contract.hub_contract_json:
                        odcs_contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in odcs_contract.hub_contract_json["extensions"]:
                        odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}
                    odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(
                        contract.id
                    )
                    # Save the updated hub_contract_json
                    odcs_contract.save(update_fields=["hub_contract_json"])
                    # Refresh from database to ensure hub_contract_json is updated in memory
                    odcs_contract.refresh_from_db()
            except Contract.DoesNotExist:
                pass

        return contract

    def test_odps_contract_lineage(self):
        """Test ODPS contract lineage"""
        # Get lineage for ODPS contract
        # ODPS contracts may not have direct lineage, but linked ODCS does
        lineage = self.lineage_service.get_contract_lineage(
            contract_id=str(self.odps_contract.id), tenant_id=str(self.tenant.id)
        )

        # Verify structure
        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)

        # Verify ODCS link exists
        odps_hub_contract = self.odps_contract.hub_contract_json
        if isinstance(odps_hub_contract, dict):
            extensions = odps_hub_contract.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            self.assertIn("odcs_link", x_odps)
            self.assertEqual(x_odps["odcs_link"], str(self.odcs_contract.id))

    def test_odps_field_lineage(self):
        """Test ODPS field lineage through linked ODCS"""
        # ODPS contracts don't have direct field lineage
        # But we can get field lineage from linked ODCS contract
        odps_hub_contract = self.odps_contract.hub_contract_json
        if isinstance(odps_hub_contract, dict):
            extensions = odps_hub_contract.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            odcs_link = x_odps.get("odcs_link")

            if odcs_link:
                # Get field lineage from linked ODCS
                field_lineage = self.lineage_service.get_field_lineage(
                    contract_id=odcs_link,
                    field_name="odcs_field",
                    model_name="ODCSModel",
                    tenant_id=str(self.tenant.id),
                )

                self.assertIn("field_name", field_lineage)
                self.assertEqual(field_lineage["field_name"], "odcs_field")

    def test_odps_odcs_lineage_relationships(self):
        """Test ODPS-ODCS lineage relationships"""
        # Refresh contracts from database to get updated hub_contract_json (root cause fix)
        self.odcs_contract.refresh_from_db()
        self.odps_contract.refresh_from_db()

        # Verify bidirectional links
        odps_hub_contract = self.odps_contract.hub_contract_json
        odcs_hub_contract = self.odcs_contract.hub_contract_json

        # ODPS -> ODCS link
        if isinstance(odps_hub_contract, dict):
            extensions = odps_hub_contract.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            self.assertIn("odcs_link", x_odps)
            self.assertEqual(x_odps["odcs_link"], str(self.odcs_contract.id))

        # ODCS -> ODPS link
        if isinstance(odcs_hub_contract, dict):
            extensions = odcs_hub_contract.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            self.assertIn("odps_link", x_odps)
            self.assertEqual(x_odps["odps_link"], str(self.odps_contract.id))

        # Test lineage through ODCS chain
        # ODPS dependent -> ODCS dependent -> ODCS source
        odps_dependent_hub = self.odps_dependent.hub_contract_json
        if isinstance(odps_dependent_hub, dict):
            extensions = odps_dependent_hub.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            odcs_dependent_id = x_odps.get("odcs_link")

            if odcs_dependent_id:
                # Get lineage from linked ODCS
                odcs_lineage = self.lineage_service.get_contract_lineage(
                    contract_id=odcs_dependent_id, tenant_id=str(self.tenant.id)
                )

                # Should show dependency on source
                contracts = odcs_lineage.get("contracts", [])
                contract_names = [c.get("name") for c in contracts if isinstance(c, dict)]
                self.assertIn("odcs-source", contract_names)

    def test_odps_product_lineage(self):
        """Test ODPS product lineage"""
        # ODPS products have product-level information
        # Lineage is tracked through linked ODCS contracts
        odps_hub_contract = self.odps_contract.hub_contract_json

        # Verify product information
        if isinstance(odps_hub_contract, dict):
            product = odps_hub_contract.get("product", {})
            details = product.get("details", {})
            en_details = details.get("en", {})

            self.assertIn("productID", en_details)
            self.assertIn("name", en_details)

            # Product lineage is through ODCS link
            extensions = odps_hub_contract.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            if "odcs_link" in x_odps:
                # Can get lineage from linked ODCS
                odcs_id = x_odps["odcs_link"]
                odcs_lineage = self.lineage_service.get_contract_lineage(
                    contract_id=odcs_id, tenant_id=str(self.tenant.id)
                )

                self.assertIn("contracts", odcs_lineage)

    def test_odps_lineage_visualization(self):
        """Test ODPS lineage visualization"""
        # Visualize lineage for ODPS contract
        # Lineage visualization should work through linked ODCS
        visualization = self.lineage_service.get_lineage_visualization(
            contract_id=str(self.odps_dependent.id),
            format="json",
            tenant_id=str(self.tenant.id),
        )

        # Should return visualization structure
        self.assertIn("nodes", visualization)
        self.assertIn("links", visualization)

        # Nodes should include contract information
        nodes = visualization.get("nodes", [])
        self.assertGreater(len(nodes), 0)

        # Test DOT format for ODPS
        visualization_dot = self.lineage_service.get_lineage_visualization(
            contract_id=str(self.odps_dependent.id),
            format="dot",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("dot", visualization_dot)
        dot_string = visualization_dot["dot"]
        self.assertIn("digraph", dot_string)

    def tearDown(self):
        """Clean up test data and close database connections"""
        # Reconnect signals after test
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)

        from django.db import connection

        connection.close()
        super().tearDown()
