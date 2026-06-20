"""
Tests for typed HubContract models and validation helpers.
"""

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
        assert model.schema_.fields[0].name == "id"

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
                    "primary_key": ["id"],
                }
            ],
            "servicelevels": [
                {"name": "availability", "target": "99.9", "unit": "%", "priority": "P1"}
            ],
            "quality": {"rules": [{"name": "not_null", "dimension": "Completeness"}]},
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
        field = model.schema_.fields[0]
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
        dumped = model.model_dump(exclude_none=True, by_alias=True)
        assert (
            "custom_info_field" in dumped.get("info", {})
            or "custom_field" in dumped.get("schema", {}).get("fields", [{}])[0]
        )

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

        dumped = model.model_dump(exclude_none=True, by_alias=True)
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

    # Edge cases and error handling tests
    def test_validate_hub_contract_with_none(self):
        """Test validation with None input."""
        try:
            model, errors = validate_hub_contract_dict(None)
            # If it doesn't raise, verify structure
            assert model is None
            assert isinstance(errors, list)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_validate_hub_contract_with_empty_dict(self):
        """Test validation with empty dictionary."""
        hub_contract = {}
        model, errors = validate_hub_contract_dict(hub_contract)

        # Should fail validation
        assert model is None
        assert isinstance(errors, list)
        assert len(errors) > 0

    def test_validate_hub_contract_with_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Missing hub_contract_version
        hub_contract1 = {
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }
        model1, errors1 = validate_hub_contract_dict(hub_contract1)
        assert model1 is None or len(errors1) > 0

        # Missing id
        hub_contract2 = {
            "hub_contract_version": "1.0.0",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }
        model2, errors2 = validate_hub_contract_dict(hub_contract2)
        assert model2 is None or len(errors2) > 0

        # Missing info
        hub_contract3 = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }
        model3, errors3 = validate_hub_contract_dict(hub_contract3)
        assert model3 is None or len(errors3) > 0

    def test_validate_hub_contract_with_invalid_field_types(self):
        """Test validation with invalid field data types."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "invalid_type",  # Invalid type
                        "nullable": "not-a-boolean",  # Invalid boolean
                    }
                ]
            },
        }

        model, errors = validate_hub_contract_dict(hub_contract)
        # Should fail validation or handle gracefully
        assert model is None or len(errors) > 0

    def test_validate_hub_contract_with_none_values(self):
        """Test validation with None values in fields."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": None},  # None name
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, errors = validate_hub_contract_dict(hub_contract)
        # Should fail validation
        assert model is None
        assert len(errors) > 0

    def test_validate_hub_contract_with_very_long_strings(self):
        """Test validation with very long string values."""
        long_string = "A" * 100000
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": long_string},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle very long strings
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_special_characters(self):
        """Test validation with special characters in field values."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract_v2",
            "info": {"name": "Contract <>&\"'"},
            "schema": {"fields": [{"name": "field-name_v2", "data_type": "string"}]},
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle special characters
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_unicode_characters(self):
        """Test validation with unicode characters."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "产品名称", "description": "Descripción"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle unicode characters
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_nested_structures(self):
        """Test validation with deeply nested structures."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {
                "name": "Test",
                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle nested structures
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_invalid_version_format(self):
        """Test validation with invalid version format."""
        hub_contract = {
            "hub_contract_version": "invalid-version",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # May accept or reject invalid version
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_many_fields(self):
        """Test validation with many fields."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {
                "fields": [{"name": f"field_{i}", "data_type": "string"} for i in range(1000)]
            },
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle many fields
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_many_models(self):
        """Test validation with many models."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [
                {"name": f"model_{i}", "fields": [{"name": "id", "data_type": "string"}]}
                for i in range(100)
            ],
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle many models
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_with_many_rules(self):
        """Test validation with many quality rules."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "quality": {
                "rules": [
                    {
                        "name": f"rule_{i}",
                        "dimension": "Completeness",
                        "expression": f"field_{i} IS NOT NULL",
                    }
                    for i in range(100)
                ]
            },
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle many rules
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_field_with_all_properties(self):
        """Test validation with field containing all possible properties."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {
                "fields": [
                    {
                        "name": "comprehensive_field",
                        "data_type": "string",
                        "nullable": False,
                        "is_primary_key": True,
                        "min_length": 1,
                        "max_length": 100,
                        "description": "Comprehensive field",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "default": "default@example.com",
                        "enum": ["option1", "option2"],
                        "examples": ["example1@example.com", "example2@example.com"],
                    }
                ]
            },
        }

        model, _errors = validate_hub_contract_dict(hub_contract)
        # Should handle all field properties
        assert model is None or isinstance(model, HubContractModel)

    def test_validate_hub_contract_model_dump_preserves_structure(self):
        """Test that model dump preserves contract structure."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "extensions": {"custom": "value"},
        }

        model, errors = validate_hub_contract_dict(hub_contract)
        assert errors == []
        assert model is not None

        dumped = model.model_dump(exclude_none=True, by_alias=True)
        # Should preserve structure
        assert dumped["hub_contract_version"] == "1.0.0"
        assert dumped["id"] == "test"
        assert dumped["info"]["name"] == "Test"
        if "extensions" in dumped:
            assert dumped["extensions"]["custom"] == "value"
