"""
Unit tests for Definition object normalization.
"""
import json

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.models import NormalizationStatus


class TestDefinitionNormalization(TestCase):
    """Tests for Definition object normalization."""

    def test_extract_authoritative_definitions_dict_format(self):
        """Test extraction of authoritativeDefinitions in dictionary format."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": {
                "Address": {
                    "type": "object",
                    "description": "Address definition",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                },
                "Email": {
                    "type": "string",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                },
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None
        assert "definitions" in hub_contract
        assert len(hub_contract["definitions"]) == 2

        # Check Address definition
        address_def = next((d for d in hub_contract["definitions"] if d["name"] == "Address"), None)
        assert address_def is not None
        assert address_def["type"] == "object"
        assert address_def["description"] == "Address definition"
        assert "properties" in address_def

        # Check Email definition
        email_def = next((d for d in hub_contract["definitions"] if d["name"] == "Email"), None)
        assert email_def is not None
        assert email_def["type"] == "string"
        assert email_def["format"] == "email"
        assert "pattern" in email_def

    def test_extract_authoritative_definitions_list_format(self):
        """Test extraction of authoritativeDefinitions in list format."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": [
                {
                    "name": "Address",
                    "type": "object",
                    "description": "Address definition",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                },
                {
                    "name": "Email",
                    "type": "string",
                    "format": "email",
                },
            ],
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None
        assert "definitions" in hub_contract
        assert len(hub_contract["definitions"]) == 2

    def test_extract_authoritative_definitions_from_description(self):
        """Test extraction of authoritativeDefinitions from description.authoritativeDefinitions."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "description": {
                "authoritativeDefinitions": {
                    "Address": {
                        "type": "object",
                        "description": "Address definition",
                    },
                },
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None
        assert "definitions" in hub_contract
        assert len(hub_contract["definitions"]) == 1
        assert hub_contract["definitions"][0]["name"] == "Address"

    def test_extract_reusable_field_definitions(self):
        """Test extraction of reusable field definitions with all properties."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": {
                "PhoneNumber": {
                    "type": "string",
                    "description": "Phone number field",
                    "pattern": "^\\+?[1-9]\\d{1,14}$",
                    "minLength": 10,
                    "maxLength": 15,
                    "nullable": False,
                },
                "Currency": {
                    "type": "string",
                    "enum": ["USD", "EUR", "GBP"],
                    "default": "USD",
                },
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "definitions" in hub_contract

        phone_def = next((d for d in hub_contract["definitions"] if d["name"] == "PhoneNumber"), None)
        assert phone_def is not None
        assert phone_def["type"] == "string"
        assert phone_def["pattern"] == "^\\+?[1-9]\\d{1,14}$"
        assert phone_def["min_length"] == 10
        assert phone_def["max_length"] == 15
        assert phone_def["nullable"] is False

        currency_def = next((d for d in hub_contract["definitions"] if d["name"] == "Currency"), None)
        assert currency_def is not None
        assert currency_def["enum"] == ["USD", "EUR", "GBP"]
        assert currency_def["default"] == "USD"

    def test_preserve_unmappable_fields_in_extensions(self):
        """Test that unmappable fields are preserved in extensions."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": {
                "CustomDefinition": {
                    "type": "string",
                    "customProperty": "customValue",
                    "anotherCustom": {"nested": "value"},
                },
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "definitions" in hub_contract

        custom_def = next((d for d in hub_contract["definitions"] if d["name"] == "CustomDefinition"), None)
        assert custom_def is not None
        assert "extensions" in custom_def
        assert custom_def["extensions"]["customProperty"] == "customValue"
        assert custom_def["extensions"]["anotherCustom"] == {"nested": "value"}

    def test_missing_definitions_handling(self):
        """Test handling when authoritativeDefinitions is missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None
        # definitions should not be present if not in source
        assert "definitions" not in hub_contract or hub_contract.get("definitions") is None

    def test_invalid_definitions_data_handling(self):
        """Test handling of invalid definitions data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": "invalid_string",  # Should be dict or list
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        # Should still normalize but skip invalid definitions
        assert status == NormalizationStatus.NORMALIZED_OK or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        assert hub_contract is not None
        # definitions should not be present if invalid
        assert "definitions" not in hub_contract or hub_contract.get("definitions") is None or len(hub_contract.get("definitions", [])) == 0

    def test_definitions_with_nested_properties(self):
        """Test definitions with nested properties (object types)."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "authoritativeDefinitions": {
                "Person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer", "minimum": 0, "maximum": 150},
                        "email": {"$ref": "#/definitions/Email"},
                    },
                },
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "definitions" in hub_contract

        person_def = next((d for d in hub_contract["definitions"] if d["name"] == "Person"), None)
        assert person_def is not None
        assert "properties" in person_def
        assert "name" in person_def["properties"]
        assert "age" in person_def["properties"]

