"""
Unit tests for complete Models section normalization.
"""
import json

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.models import NormalizationStatus


class TestModelsCompleteNormalization(TestCase):
    """Tests for complete Models section normalization."""

    def test_odcs_schema_array_extraction(self):
        """Test extraction of ODCS schema[] array into models[]."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": [
                {
                    "name": "users",
                    "description": "Users table",
                    "logicalType": "table",
                    "physicalType": "postgresql",
                    "physicalName": "users_table",
                    "fields": [
                        {"name": "id", "type": "string", "is_primary_key": True},
                        {"name": "name", "type": "string"},
                    ],
                },
                {
                    "name": "orders",
                    "description": "Orders table",
                    "logicalType": "table",
                    "fields": [
                        {"name": "id", "type": "string", "is_primary_key": True},
                        {"name": "user_id", "type": "string"},
                    ],
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
        assert "models" in hub_contract
        assert len(hub_contract["models"]) == 2

        # Check first model
        users_model = next((m for m in hub_contract["models"] if m["name"] == "users"), None)
        assert users_model is not None
        assert users_model["description"] == "Users table"
        assert users_model["logical_type"] == "table"
        assert users_model["physical_type"] == "postgresql"
        assert users_model["physical_name"] == "users_table"
        assert len(users_model["fields"]) == 2

        # Check second model
        orders_model = next((m for m in hub_contract["models"] if m["name"] == "orders"), None)
        assert orders_model is not None
        assert orders_model["description"] == "Orders table"

    def test_unified_models_canonical_structure(self):
        """Test that models[] has unified canonical structure."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "name": "products",
                "description": "Products table",
                "logicalType": "table",
                "physicalType": "snowflake",
                "physicalName": "PROD.PUBLIC.PRODUCTS",
                "dataGranularityDescription": "One row per product",
                "fields": [
                    {"name": "id", "type": "string", "is_primary_key": True},
                    {"name": "name", "type": "string"},
                    {"name": "price", "type": "number"},
                ],
                "primary_key": ["id"],
                "unique_constraints": [["name"]],
                "indexes": [{"fields": ["name"]}],
                "tags": ["product", "catalog"],
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "models" in hub_contract
        assert len(hub_contract["models"]) == 1

        model = hub_contract["models"][0]
        assert model["name"] == "products"
        assert model["description"] == "Products table"
        assert model["logical_type"] == "table"
        assert model["physical_type"] == "snowflake"
        assert model["physical_name"] == "PROD.PUBLIC.PRODUCTS"
        assert model["data_granularity_description"] == "One row per product"
        assert "primary_key" in model
        assert "unique_constraints" in model
        assert "indexes" in model
        assert "tags" in model
        assert len(model["fields"]) == 3

    def test_extract_all_model_properties(self):
        """Test extraction of all model properties including advanced attributes."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "name": "events",
                "description": "Event stream",
                "logicalType": "stream",
                "physicalType": "kafka",
                "physicalName": "events-topic",
                "dataGranularityDescription": "One event per message",
                "fields": [
                    {"name": "event_id", "type": "string"},
                    {"name": "timestamp", "type": "string", "format": "date-time"},
                ],
                "tags": ["events", "streaming"],
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "models" in hub_contract

        model = hub_contract["models"][0]
        # Check all properties are extracted
        assert model["name"] == "events"
        assert model["description"] == "Event stream"
        assert model["logical_type"] == "stream"
        assert model["physical_type"] == "kafka"
        assert model["physical_name"] == "events-topic"
        assert model["data_granularity_description"] == "One event per message"
        assert model["tags"] == ["events", "streaming"]

    def test_preserve_unmappable_fields_in_model_extensions(self):
        """Test that unmappable model fields are preserved in extensions."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "name": "custom_model",
                "fields": [{"name": "id", "type": "string"}],
                "customProperty": "customValue",
                "anotherCustom": {"nested": "value"},
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "models" in hub_contract

        model = hub_contract["models"][0]
        # Unmappable fields should be in extensions
        assert "extensions" in model or model.get("customProperty") is not None

    def test_missing_models_handling(self):
        """Test handling when schema is missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        # Should still normalize but may have errors/warnings
        assert hub_contract is not None
        # models may not be present if no schema
        # But schema should be present (required field)

    def test_invalid_models_data_handling(self):
        """Test handling of invalid models/schema data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": "invalid_string",  # Should be dict or list
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        # Should still normalize but may have errors
        assert hub_contract is not None
        # May have normalization errors

    def test_schema_derived_view_from_models(self):
        """Test that schema is derived from models[0] when single model."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "name": "single_model",
                "fields": [
                    {"name": "id", "type": "string", "is_primary_key": True},
                    {"name": "value", "type": "integer"},
                ],
                "primary_key": ["id"],
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "models" in hub_contract
        assert "schema" in hub_contract

        # Schema should be derived from first model
        assert "fields" in hub_contract["schema"]
        assert len(hub_contract["schema"]["fields"]) == 2
        assert "primary_key" in hub_contract["schema"]

    def test_multiple_schema_objects(self):
        """Test handling of multiple schema objects in schema[] array."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": [
                {
                    "name": "model1",
                    "fields": [{"name": "id1", "type": "string"}],
                },
                {
                    "name": "model2",
                    "fields": [{"name": "id2", "type": "string"}],
                },
                {
                    "name": "model3",
                    "fields": [{"name": "id3", "type": "string"}],
                },
            ],
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "models" in hub_contract
        assert len(hub_contract["models"]) == 3

        # Schema should be derived from first model
        assert "schema" in hub_contract
        assert hub_contract["schema"]["fields"][0]["name"] == "id1"

