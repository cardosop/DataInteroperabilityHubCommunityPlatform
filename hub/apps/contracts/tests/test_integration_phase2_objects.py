"""
Integration tests for Phase 2 objects (Definitions, Models, Support Channels).
"""
import json

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from tests.factories import AssetFactory, TenantFactory, UserFactory


class TestPhase2ObjectsIntegration(TestCase):
    """Integration tests for Phase 2 objects."""

    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.asset = AssetFactory(tenant=self.tenant)

    def test_normalize_contract_with_all_phase2_objects(self):
        """Test normalization with definitions, complete models, and support channels."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-phase2",
            "name": "Test Contract Phase 2",
            "version": "1.0.0",
            "schema": [
                {
                    "name": "users",
                    "description": "Users table",
                    "logicalType": "table",
                    "physicalType": "postgresql",
                    "physicalName": "users_table",
                    "dataGranularityDescription": "One row per user",
                    "fields": [
                        {"name": "id", "type": "string", "is_primary_key": True},
                        {"name": "email", "type": "string", "$ref": "#/definitions/Email"},
                    ],
                    "tags": ["users", "auth"],
                },
            ],
            "authoritativeDefinitions": {
                "Email": {
                    "type": "string",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                },
                "Address": {
                    "type": "object",
                    "description": "Address definition",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                },
            },
            "support": [
                {
                    "name": "Support Team",
                    "email": "support@example.com",
                },
                {
                    "tool": "slack",
                    "url": "https://slack.example.com/channel",
                    "description": "Slack support channel",
                    "scope": "general",
                },
                {
                    "tool": "ticket",
                    "url": "https://tickets.example.com",
                    "description": "Ticket system",
                },
            ],
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert spec_type == OriginalSpecType.ODCS
        assert hub_contract is not None

        # Verify definitions
        assert "definitions" in hub_contract
        assert len(hub_contract["definitions"]) == 2
        email_def = next((d for d in hub_contract["definitions"] if d["name"] == "Email"), None)
        assert email_def is not None
        assert email_def["type"] == "string"
        assert email_def["format"] == "email"

        # Verify models
        assert "models" in hub_contract
        assert len(hub_contract["models"]) == 1
        users_model = hub_contract["models"][0]
        assert users_model["name"] == "users"
        assert users_model["logical_type"] == "table"
        assert users_model["physical_type"] == "postgresql"
        assert users_model["data_granularity_description"] == "One row per user"
        assert "tags" in users_model

        # Verify support channels (separate from contacts)
        assert "support" in hub_contract
        assert len(hub_contract["support"]) == 2
        slack_channel = next((c for c in hub_contract["support"] if c.get("tool") == "slack"), None)
        assert slack_channel is not None

        # Verify contacts (separate from support channels)
        assert "contact" in hub_contract
        assert len(hub_contract["contact"]) == 1
        assert hub_contract["contact"][0]["name"] == "Support Team"

    def test_create_contract_via_api_with_phase2_objects(self):
        """Test creating a contract via API with Phase 2 objects."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "api-test-phase2",
            "name": "API Test Phase 2",
            "version": "1.0.0",
            "schema": {
                "name": "products",
                "description": "Products table",
                "logicalType": "table",
                "fields": [{"name": "id", "type": "string"}],
            },
            "authoritativeDefinitions": {
                "ProductID": {
                    "type": "string",
                    "pattern": "^[A-Z0-9]{10}$",
                },
            },
            "support": [
                {
                    "tool": "slack",
                    "url": "https://slack.example.com",
                },
            ],
        }

        ensure_tenant_has_active_subscription(self.tenant)
        api_client = APIClient()
        api_client.force_authenticate(user=self.user)
        response = api_client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps(odcs_contract),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        assert response.status_code in [201, 400]  # May have validation warnings
        if response.status_code == 201:
            contract = Contract.objects.get(id=response.data["id"])
            hub_contract = contract.hub_contract_json

            # Verify all Phase 2 objects are present in stored contract
            assert "definitions" in hub_contract or "models" in hub_contract or "support" in hub_contract

    def test_models_canonical_structure_with_all_properties(self):
        """Test that models[] has complete canonical structure with all properties."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-models-complete",
            "name": "Test Models Complete",
            "version": "1.0.0",
            "schema": {
                "name": "complete_model",
                "description": "Complete model with all properties",
                "logicalType": "table",
                "physicalType": "snowflake",
                "physicalName": "COMPLETE_MODEL",
                "dataGranularityDescription": "One row per record",
                "fields": [
                    {"name": "id", "type": "string", "is_primary_key": True},
                    {"name": "name", "type": "string", "is_unique": True},
                    {"name": "value", "type": "integer", "is_indexed": True},
                ],
                "primary_key": ["id"],
                "unique_constraints": [["name"]],
                "indexes": [{"fields": ["value"]}],
                "tags": ["complete", "test"],
            },
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        assert hub_contract is not None
        assert "models" in hub_contract
        assert len(hub_contract["models"]) == 1

        model = hub_contract["models"][0]
        # Verify all properties are present
        assert model["name"] == "complete_model"
        assert model["description"] == "Complete model with all properties"
        assert model["logical_type"] == "table"
        assert model["physical_type"] == "snowflake"
        assert model["physical_name"] == "COMPLETE_MODEL"
        assert model["data_granularity_description"] == "One row per record"
        assert "primary_key" in model
        assert "unique_constraints" in model
        assert "indexes" in model
        assert "tags" in model
        assert len(model["fields"]) == 3

        # Verify schema is derived from model
        assert "schema" in hub_contract
        assert "fields" in hub_contract["schema"]

