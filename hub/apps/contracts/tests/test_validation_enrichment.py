"""
Unit tests for validation and enrichment functions.
"""
import pytest

from hub.apps.contracts.validation import (
    validate_and_enrich_contacts,
    validate_and_enrich_servicelevels,
    validate_and_enrich_roles,
    validate_and_enrich_team,
    validate_and_enrich_pricing,
    validate_and_enrich_lineage,
    validate_and_enrich_advanced_schema_attributes,
    validate_email,
    validate_url,
)


class TestEmailValidation:
    """Tests for email validation."""

    def test_valid_email(self):
        is_valid, error = validate_email("test@example.com")
        assert is_valid is True
        assert error is None

    def test_invalid_email_no_at(self):
        is_valid, error = validate_email("invalid-email")
        assert is_valid is False
        assert error is not None

    def test_invalid_email_empty(self):
        is_valid, error = validate_email("")
        assert is_valid is False
        assert error is not None

    def test_invalid_email_none(self):
        is_valid, error = validate_email(None)
        assert is_valid is False
        assert error is not None


class TestURLValidation:
    """Tests for URL validation."""

    def test_valid_url_http(self):
        is_valid, error = validate_url("http://example.com")
        assert is_valid is True
        assert error is None

    def test_valid_url_https(self):
        is_valid, error = validate_url("https://example.com/path")
        assert is_valid is True
        assert error is None

    def test_invalid_url_empty(self):
        is_valid, error = validate_url("")
        assert is_valid is False
        assert error is not None

    def test_invalid_url_none(self):
        is_valid, error = validate_url(None)
        assert is_valid is False
        assert error is not None


class TestContactValidationEnrichment:
    """Tests for contact validation and enrichment."""

    def test_validate_valid_contacts(self):
        contacts = [
            {"name": "Support", "email": "support@example.com", "url": "https://example.com/support"},
            {"name": "Sales", "email": "sales@example.com"},
        ]
        enriched, errors = validate_and_enrich_contacts(contacts)
        assert len(errors) == 0
        assert len(enriched) == 2
        assert enriched[0]["email"] == "support@example.com"

    def test_validate_invalid_email(self):
        contacts = [{"name": "Support", "email": "invalid-email"}]
        enriched, errors = validate_and_enrich_contacts(contacts)
        assert len(errors) > 0
        assert any("email" in e.lower() for e in errors)
        assert "_email_validation_error" in enriched[0]

    def test_validate_invalid_url(self):
        contacts = [{"name": "Support", "url": "not-a-url"}]
        enriched, errors = validate_and_enrich_contacts(contacts)
        assert len(errors) > 0
        assert any("url" in e.lower() for e in errors)

    def test_enrich_tool_normalization(self):
        contacts = [{"name": "Support", "tool": "E-MAIL"}]
        enriched, errors = validate_and_enrich_contacts(contacts)
        assert len(errors) == 0
        assert enriched[0]["tool"] == "email"

    def test_validate_non_list(self):
        enriched, errors = validate_and_enrich_contacts({})
        assert len(errors) > 0
        assert len(enriched) == 0


class TestServiceLevelValidationEnrichment:
    """Tests for service level validation and enrichment."""

    def test_validate_valid_servicelevels(self):
        servicelevels = [
            {"name": "availability", "target": "99.9", "unit": "%", "operator": ">="},
            {"name": "latency", "target": "100", "unit": "ms", "operator": "<="},
        ]
        enriched, errors = validate_and_enrich_servicelevels(servicelevels)
        assert len(errors) == 0
        assert len(enriched) == 2

    def test_enrich_unit_normalization(self):
        servicelevels = [{"name": "availability", "target": "99", "unit": "percent"}]
        enriched, errors = validate_and_enrich_servicelevels(servicelevels)
        assert len(errors) == 0
        assert enriched[0]["unit"] == "%"

    def test_enrich_operator_normalization(self):
        servicelevels = [{"name": "latency", "target": "100", "operator": "greater_than"}]
        enriched, errors = validate_and_enrich_servicelevels(servicelevels)
        assert len(errors) == 0
        # Should normalize operator
        assert enriched[0].get("operator") is not None

    def test_enrich_default_priority(self):
        servicelevels = [{"name": "availability", "target": "99.9"}]
        enriched, errors = validate_and_enrich_servicelevels(servicelevels)
        assert len(errors) == 0
        assert enriched[0]["priority"] == "P3"

    def test_validate_invalid_target(self):
        servicelevels = [{"name": "availability", "target": "not-a-number"}]
        enriched, errors = validate_and_enrich_servicelevels(servicelevels)
        assert len(errors) > 0
        assert any("target" in e.lower() for e in errors)


class TestRoleValidationEnrichment:
    """Tests for role validation and enrichment."""

    def test_validate_valid_roles(self):
        roles = [
            {"roleName": "reader", "accessType": "READ"},
            {"roleName": "writer", "accessType": "WRITE", "approvers": ["admin@example.com"]},
        ]
        enriched, errors = validate_and_enrich_roles(roles)
        assert len(errors) == 0
        assert len(enriched) == 2

    def test_enrich_field_name_normalization(self):
        roles = [{"role_name": "reader", "access_type": "read"}]
        enriched, errors = validate_and_enrich_roles(roles)
        assert len(errors) == 0
        assert "roleName" in enriched[0]
        assert "accessType" in enriched[0]

    def test_enrich_access_type_normalization(self):
        roles = [{"roleName": "reader", "accessType": "r"}]
        enriched, errors = validate_and_enrich_roles(roles)
        assert len(errors) == 0
        assert enriched[0]["accessType"] == "READ"

    def test_enrich_approvers_string_to_list(self):
        roles = [{"roleName": "reader", "approvers": "admin@example.com,user@example.com"}]
        enriched, errors = validate_and_enrich_roles(roles)
        assert len(errors) == 0
        assert isinstance(enriched[0]["approvers"], list)
        assert len(enriched[0]["approvers"]) == 2

    def test_validate_missing_rolename(self):
        roles = [{"accessType": "READ"}]
        enriched, errors = validate_and_enrich_roles(roles)
        assert len(errors) > 0
        assert any("rolename" in e.lower() for e in errors)


class TestTeamValidationEnrichment:
    """Tests for team validation and enrichment."""

    def test_validate_valid_team(self):
        team = [
            {"member": "John Doe", "role": "Engineer", "dateIn": "2024-01-01"},
            {"member": "Jane Smith", "role": "Manager", "dateIn": "2024-01-01", "dateOut": "2024-12-31"},
        ]
        enriched, errors = validate_and_enrich_team(team)
        assert len(errors) == 0
        assert len(enriched) == 2

    def test_enrich_field_name_normalization(self):
        team = [{"member_name": "John Doe", "date_in": "2024-01-01"}]
        enriched, errors = validate_and_enrich_team(team)
        assert len(errors) == 0
        assert "memberName" in enriched[0]
        assert "dateIn" in enriched[0]

    def test_validate_invalid_date_format(self):
        team = [{"member": "John Doe", "dateIn": "01-01-2024"}]
        enriched, errors = validate_and_enrich_team(team)
        assert len(errors) > 0
        assert any("date" in e.lower() for e in errors)

    def test_validate_valid_iso_date(self):
        team = [{"member": "John Doe", "dateIn": "2024-01-01T00:00:00Z"}]
        enriched, errors = validate_and_enrich_team(team)
        assert len(errors) == 0


class TestPricingValidationEnrichment:
    """Tests for pricing validation and enrichment."""

    def test_validate_valid_pricing(self):
        pricing = {"priceAmount": "100.00", "priceCurrency": "USD", "priceUnit": "per_month"}
        enriched, errors = validate_and_enrich_pricing(pricing)
        assert len(errors) == 0
        assert enriched["priceCurrency"] == "USD"

    def test_enrich_field_name_normalization(self):
        pricing = {"price_amount": "100", "price_currency": "usd", "price_unit": "month"}
        enriched, errors = validate_and_enrich_pricing(pricing)
        assert len(errors) == 0
        assert "priceAmount" in enriched
        assert "priceCurrency" in enriched
        assert "priceUnit" in enriched

    def test_enrich_currency_normalization(self):
        pricing = {"priceAmount": "100", "priceCurrency": "usd"}
        enriched, errors = validate_and_enrich_pricing(pricing)
        assert len(errors) == 0
        assert enriched["priceCurrency"] == "USD"

    def test_enrich_unit_normalization(self):
        pricing = {"priceAmount": "100", "priceUnit": "month"}
        enriched, errors = validate_and_enrich_pricing(pricing)
        assert len(errors) == 0
        assert enriched["priceUnit"] == "per_month"

    def test_validate_invalid_amount(self):
        pricing = {"priceAmount": "not-a-number", "priceCurrency": "USD"}
        enriched, errors = validate_and_enrich_pricing(pricing)
        assert len(errors) > 0
        assert any("amount" in e.lower() for e in errors)


class TestLineageValidationEnrichment:
    """Tests for lineage validation and enrichment."""

    def test_validate_valid_lineage(self):
        lineage = [
            {
                "inputFields": [
                    {"namespace": "ns1", "name": "contract1", "model": "model1", "field": "field1"}
                ],
                "transformations": [{"logic": "field1 * 2"}],
            }
        ]
        enriched, errors = validate_and_enrich_lineage(lineage)
        assert len(errors) == 0
        assert len(enriched) == 1

    def test_enrich_field_name_normalization(self):
        lineage = [{"input_fields": [{"namespace": "ns1", "name": "contract1"}]}]
        enriched, errors = validate_and_enrich_lineage(lineage)
        assert len(errors) == 0
        assert "inputFields" in enriched[0]

    def test_enrich_string_reference_parsing(self):
        lineage = [{"inputFields": ["ns1/contract1/model1/field1"]}]
        enriched, errors = validate_and_enrich_lineage(lineage)
        assert len(errors) == 0
        assert isinstance(enriched[0]["inputFields"][0], dict)
        assert enriched[0]["inputFields"][0]["namespace"] == "ns1"

    def test_enrich_transform_logic_normalization(self):
        lineage = [
            {
                "inputFields": [{"namespace": "ns1", "name": "contract1"}],
                "transformations": [{"transformLogic": "field1 * 2"}],
            }
        ]
        enriched, errors = validate_and_enrich_lineage(lineage)
        assert len(errors) == 0
        assert "logic" in enriched[0]["transformations"][0]


class TestAdvancedSchemaAttributesValidationEnrichment:
    """Tests for advanced schema attributes validation and enrichment."""

    def test_validate_valid_model(self):
        model = {
            "name": "test_model",
            "logicalType": "table",
            "physicalType": "postgresql",
            "physicalName": "test_table",
            "dataGranularityDescription": "Daily aggregates",
        }
        enriched, errors = validate_and_enrich_advanced_schema_attributes(model)
        assert len(errors) == 0
        assert enriched["logical_type"] == "table"

    def test_enrich_field_name_normalization(self):
        model = {
            "name": "test_model",
            "logicalType": "table",
            "physicalType": "postgresql",
        }
        enriched, errors = validate_and_enrich_advanced_schema_attributes(model)
        assert len(errors) == 0
        assert "logical_type" in enriched
        assert "physical_type" in enriched

    def test_enrich_logical_type_normalization(self):
        model = {"name": "test_model", "logicalType": "TABLE"}
        enriched, errors = validate_and_enrich_advanced_schema_attributes(model)
        assert len(errors) == 0
        assert enriched["logical_type"] == "table"

    def test_enrich_physical_type_normalization(self):
        model = {"name": "test_model", "physicalType": "POSTGRESQL"}
        enriched, errors = validate_and_enrich_advanced_schema_attributes(model)
        assert len(errors) == 0
        assert enriched["physical_type"] == "postgresql"

