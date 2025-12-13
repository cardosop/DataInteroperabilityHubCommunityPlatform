"""
Tests for typed HubContract models and validation helpers.
"""
import pytest

from hub.apps.contracts.typed_models import HubContractModel, validate_hub_contract_dict


class TestTypedModels:
    """Validation for typed HubContract models."""

    def test_validate_hub_contract_success(self):
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "typed-1",
            "info": {"name": "Typed Contract", "tags": ["a"], "owners": [{"name": "owner"}]},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
            "extensions": {"extra": "value"},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert isinstance(model, HubContractModel)
        assert model.info.name == "Typed Contract"
        assert model.schema.fields[0].name == "id"

    def test_validate_hub_contract_missing_fields(self):
        hub_contract = {
            "hub_contract_version": "",
            "id": "",
            "info": {},
            "schema": {"fields": []},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert model is None
        assert errors
        # Should surface specific locations for easier debugging
        assert any("info -> name" in message or "schema -> fields" in message for message in errors)

    def test_validate_hub_contract_with_models_and_servicelevels(self):
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "typed-2",
            "info": {"name": "With Models"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [
                {
                    "name": "default",
                    "fields": [{"name": "id", "data_type": "string", "is_primary_key": True}],
                    "primary_key": ["id"]
                }
            ],
            "servicelevels": [
                {"name": "availability", "target": "99.9", "unit": "%", "priority": "P1"}
            ],
            "quality": {
                "rules": [
                    {"name": "not_null", "dimension": "Completeness"}
                ]
            }
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert model is not None
        assert model.models and model.models[0].name == "default"
        assert model.servicelevels and model.servicelevels[0].name == "availability"

    def test_validate_hub_contract_with_all_sections(self):
        """Test validation with all optional sections."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "full-contract",
            "info": {"name": "Full Contract", "description": "Test", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [{"name": "default", "fields": [{"name": "id", "data_type": "string"}]}],
            "quality": {"default_profile_key": "basic", "rules": []},
            "contact": [{"name": "Support", "email": "support@example.com"}],
            "servers": [{"type": "postgresql", "url": "postgresql://localhost"}],
            "terms": {"usage": "Internal use only"},
            "servicelevels": [{"name": "availability", "target": "99.9"}],
            "privacy_compliance": {"contains_personal_data": False},
            "lifecycle": {"data_source": "database"},
            "marketplace": {"license_summary": "MIT"},
            "original_spec": {"type": "ODCS", "version": "3.0.2"},
            "extensions": {"custom": "value"},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert model is not None
        assert model.contact is not None
        assert model.servers is not None
        assert model.terms is not None
        assert model.servicelevels is not None

    def test_validate_hub_contract_field_validation(self):
        """Test field-level validation."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "field-test",
            "info": {"name": "Field Test"},
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "nullable": False,
                        "is_primary_key": True,
                        "min_length": 1,
                        "max_length": 100,
                    }
                ]
            },
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert model is not None
        field = model.schema.fields[0]
        assert field.name == "id"
        assert field.data_type == "string"
        assert field.nullable is False
        assert field.is_primary_key is True

    def test_validate_hub_contract_extra_fields_preserved(self):
        """Test that extra fields are preserved via extra='allow'."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "extra-test",
            "info": {"name": "Extra Test", "custom_info_field": "value"},
            "schema": {"fields": [{"name": "id", "data_type": "string", "custom_field": "value"}]},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert model is not None
        # Extra fields should be preserved in the model
        dumped = model.model_dump(exclude_none=True)
        assert "custom_info_field" in dumped.get("info", {}) or "custom_field" in dumped.get("schema", {}).get("fields", [{}])[0]

    def test_validate_hub_contract_model_dump(self):
        """Test that validated model can be dumped back to dict."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "dump-test",
            "info": {"name": "Dump Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert errors == []
        assert model is not None

        dumped = model.model_dump(exclude_none=True)
        assert isinstance(dumped, dict)
        assert dumped["hub_contract_version"] == "1.0.0"
        assert dumped["id"] == "dump-test"
        assert dumped["info"]["name"] == "Dump Test"

    def test_validate_hub_contract_empty_name_fails(self):
        """Test that empty name fails validation."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "empty-name",
            "info": {"name": ""},  # Empty name
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert model is None
        assert errors
        assert any("name" in error.lower() for error in errors)

    def test_validate_hub_contract_empty_fields_fails(self):
        """Test that empty fields array fails validation."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "empty-fields",
            "info": {"name": "Empty Fields"},
            "schema": {"fields": []},  # Empty fields
        }

        model, errors = validate_hub_contract_dict(hub_contract)

        assert model is None
        assert errors
        assert any("fields" in error.lower() for error in errors)
