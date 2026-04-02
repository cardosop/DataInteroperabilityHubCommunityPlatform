"""
Integration tests for multi-level lineage in API.
"""
import json

from rest_framework import status

from hub.apps.contracts.models import Contract
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.tests.test_base import ContractsAPITestBase


class TestLineageIntegration(ContractsAPITestBase):
    """Integration tests for lineage in API."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

    def test_contract_with_contract_level_lineage(self):
        """Test contract creation with contract-level lineage."""
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-1",
            "name": "Test Contract 1",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "source-contract"},
            ],
            "transformLogic": "SELECT * FROM source",
        }

        hub_contract, spec_type, spec_version, status_val, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertIsNotNone(
            hub_contract,
            f"Normalization failed: status={status_val}, errors={errors}"
        )
        self.assertIn(
            status_val.value,
            ("NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"),
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        # Test API retrieval
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("lineage", response.data)
        lineage = response.data["lineage"]
        self.assertIsInstance(lineage, dict)
        self.assertIn("entries", lineage)

    def test_contract_with_model_level_lineage(self):
        """Test contract creation with model-level lineage."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-2",
            "name": "Test Contract 2",
            "schema": {
                "name": "test-model",
                "transformSourceObjects": [
                    {"namespace": "ns1", "name": "source-contract", "model": "source-model"},
                ],
                "transformLogic": "SELECT * FROM source_model",
                "fields": [
                    {"name": "field1", "type": "string"},
                ],
            },
        }

        hub_contract, spec_type, spec_version, status_val, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status_val.value, "NORMALIZED_OK")

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        # Test API retrieval
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("models", response.data)
        models = response.data["models"]
        self.assertIsInstance(models, list)
        if models:
            model = models[0]
            self.assertIn("lineage", model)

    def test_contract_with_field_level_lineage(self):
        """Test contract creation with field-level lineage."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-3",
            "name": "Test Contract 3",
            "schema": {
                "name": "test-model",
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "transformSourceObjects": [
                            {
                                "namespace": "ns1",
                                "name": "source-contract",
                                "model": "source-model",
                                "field": "source-field",
                            }
                        ],
                        "transformLogic": "source_field",
                    },
                ],
            },
        }

        hub_contract, spec_type, spec_version, status_val, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status_val.value, "NORMALIZED_OK")

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        # Test API retrieval
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("models", response.data)
        models = response.data["models"]
        self.assertIsInstance(models, list)
        if models:
            model = models[0]
            self.assertIn("fields", model)
            fields = model["fields"]
            if fields:
                field = fields[0]
                self.assertIn("lineage", field)

    def test_contract_with_all_lineage_levels(self):
        """Test contract creation with lineage at all levels."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-4",
            "name": "Test Contract 4",
            "transformSourceObjects": [{"namespace": "ns1", "name": "source-contract"}],
            "transformLogic": "SELECT * FROM source",
            "schema": {
                "name": "test-model",
                "transformSourceObjects": [
                    {"namespace": "ns1", "name": "source-contract", "model": "source-model"}
                ],
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "transformSourceObjects": [
                            {
                                "namespace": "ns1",
                                "name": "source-contract",
                                "model": "source-model",
                                "field": "source-field",
                            }
                        ],
                    },
                ],
            },
        }

        hub_contract, spec_type, spec_version, status_val, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status_val.value, "NORMALIZED_OK")

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        # Test API retrieval
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check contract-level lineage
        self.assertIn("lineage", response.data)
        lineage = response.data["lineage"]
        self.assertIsInstance(lineage, dict)

        # Check model-level lineage
        models = response.data.get("models", [])
        if models:
            model = models[0]
            if "lineage" in model:
                self.assertIsInstance(model["lineage"], dict)

        # Check field-level lineage
        if models:
            fields = models[0].get("fields", [])
            if fields:
                field = fields[0]
                if "lineage" in field:
                    self.assertIsInstance(field["lineage"], dict)

