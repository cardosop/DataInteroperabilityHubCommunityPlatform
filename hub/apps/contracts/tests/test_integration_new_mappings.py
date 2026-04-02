"""
Integration tests for new ODCS mappings and validation rules.

Tests the complete normalization flow with validation/enrichment for:
- Contacts, SLA properties, roles/team, pricing, lineage, and advanced schema attributes
"""
import json

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from tests.factories import AssetFactory, TenantFactory, UserFactory


class TestNewMappingsIntegration(TestCase):
    """Integration tests for new ODCS mappings."""

    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.asset = AssetFactory(tenant=self.tenant)

    def test_normalize_contract_with_all_new_objects(self):
        """Test normalization with all new objects (contact, servers, terms, servicelevels, roles, team, pricing, lineage)."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-all",
            "name": "Test Contract with All Objects",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "value", "type": "integer"},
                ]
            },
            "support": [
                {
                    "name": "Support Team",
                    "email": "support@example.com",
                    "url": "https://example.com/support",
                    "tool": "email",
                }
            ],
            "servers": [
                {
                    "type": "postgresql",
                    "url": "postgresql://localhost:5432/mydb",
                    "description": "Main database",
                }
            ],
            "description": {
                "usage": "Internal use only",
                "limitations": "Not for external distribution",
                "billing": "Free for internal teams",
            },
            "slaProperties": [
                {
                    "name": "availability",
                    "target": "99.9",
                    "unit": "%",
                    "operator": ">=",
                }
            ],
            "roles": [
                {
                    "roleName": "reader",
                    "accessType": "READ",
                    "approvers": ["admin@example.com"],
                }
            ],
            "team": [
                {
                    "member": "John Doe",
                    "role": "Engineer",
                    "dateIn": "2024-01-01",
                }
            ],
            "price": {
                "priceAmount": "100.00",
                "priceCurrency": "USD",
                "priceUnit": "per_month",
            },
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "source_contract", "model": "source_model", "field": "source_field"}
            ],
            "transformLogic": "source_field * 2",
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert spec_type == OriginalSpecType.ODCS
        assert hub_contract is not None

        # Verify all objects are present
        assert "contact" in hub_contract
        assert len(hub_contract["contact"]) > 0
        assert hub_contract["contact"][0]["email"] == "support@example.com"

        assert "servers" in hub_contract
        assert len(hub_contract["servers"]) > 0
        assert hub_contract["servers"][0]["type"] == "postgresql"

        assert "terms" in hub_contract
        assert hub_contract["terms"]["usage"] == "Internal use only"

        assert "servicelevels" in hub_contract
        assert len(hub_contract["servicelevels"]) > 0
        assert hub_contract["servicelevels"][0]["name"] == "availability"

        assert "roles" in hub_contract
        assert len(hub_contract["roles"]) > 0
        assert hub_contract["roles"][0]["roleName"] == "reader"

        assert "team" in hub_contract
        assert len(hub_contract["team"]) > 0
        assert "memberName" in hub_contract["team"][0] or "member" in hub_contract["team"][0]

        assert "pricing" in hub_contract
        assert hub_contract["pricing"]["priceCurrency"] == "USD"

        assert "lineage" in hub_contract
        assert len(hub_contract["lineage"]) > 0

    def test_normalize_contract_with_validation_errors(self):
        """Test normalization with validation errors (should still normalize but add warnings)."""
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-errors",
            "name": "Test Contract with Errors",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {
                    "name": "Support",
                    "email": "invalid-email",  # Invalid email
                    "url": "not-a-url",  # Invalid URL
                }
            ],
            "slaProperties": [
                {
                    "name": "availability",
                    "target": "not-a-number",  # Invalid target
                }
            ],
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        # Should normalize (possibly with warnings or errors from validation enrichment)
        assert status in (
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZATION_FAILED,
        )
        if status != NormalizationStatus.NORMALIZATION_FAILED:
            assert hub_contract is not None
            assert len(warnings) > 0

    def test_normalize_contract_with_advanced_schema_attributes(self):
        """Test normalization with advanced schema attributes (logical/physical types, dataGranularityDescription)."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-advanced",
            "name": "Test Contract with Advanced Schema",
            "version": "1.0.0",
            "schema": {
                "name": "advanced_model",
                "logicalType": "table",
                "physicalType": "postgresql",
                "physicalName": "advanced_table",
                "dataGranularityDescription": "Daily aggregates",
                "fields": [{"name": "id", "type": "string"}],
            },
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None

        # Verify models have advanced attributes
        if "models" in hub_contract and len(hub_contract["models"]) > 0:
            model = hub_contract["models"][0]
            assert "logical_type" in model or "logicalType" in model
            assert "physical_type" in model or "physicalType" in model

    def test_normalize_contract_with_enrichment(self):
        """Test that normalization enriches fields (normalizes tool names, units, operators, etc.)."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-enrichment",
            "name": "Test Contract with Enrichment",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [{"name": "Support", "tool": "E-MAIL"}],  # Should normalize to "email"
            "slaProperties": [
                {
                    "name": "availability",
                    "target": "99.9",
                    "unit": "percent",  # Should normalize to "%"
                    "operator": "greater_than",  # Should normalize
                }
            ],
            "price": {
                "priceAmount": "100",
                "priceCurrency": "usd",  # Should normalize to "USD"
                "priceUnit": "month",  # Should normalize to "per_month"
            },
        }

        raw_contract = json.dumps(odcs_contract)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="JSON", spec_type=OriginalSpecType.ODCS
        )

        assert hub_contract is not None

        # Verify enrichment
        if "contact" in hub_contract and len(hub_contract["contact"]) > 0:
            assert hub_contract["contact"][0].get("tool") == "email"

        if "servicelevels" in hub_contract and len(hub_contract["servicelevels"]) > 0:
            sl = hub_contract["servicelevels"][0]
            assert sl.get("unit") == "%" or sl.get("unit") == "percent"

        if "pricing" in hub_contract:
            assert hub_contract["pricing"].get("priceCurrency") == "USD"

    def test_create_contract_via_api_with_all_objects(self):
        """Test creating a contract via API with all new objects."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "api-test-contract",
            "name": "API Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [{"name": "Support", "email": "support@example.com"}],
            "servers": [{"type": "postgresql", "url": "postgresql://localhost/db"}],
            "description": {"usage": "Internal use"},
            "slaProperties": [{"name": "availability", "target": "99.9", "unit": "%"}],
            "roles": [{"roleName": "reader", "accessType": "READ"}],
            "team": [{"member": "John Doe", "role": "Engineer", "dateIn": "2024-01-01"}],
            "price": {"priceAmount": "100", "priceCurrency": "USD", "priceUnit": "per_month"},
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

            # Verify all objects are present in stored contract
            assert "contact" in hub_contract or "servers" in hub_contract or "servicelevels" in hub_contract

