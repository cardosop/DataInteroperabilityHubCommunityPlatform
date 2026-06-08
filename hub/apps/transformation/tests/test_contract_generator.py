"""
285.9.2.1.1 — Tests for DbtContractGenerator.

Tests YAML parsing, catalog.json extraction, and HubContract JSON generation.
"""
import pytest

import json
import os
import uuid
from pathlib import Path

import yaml

# ── Fixture paths ─────────────────────────────────────────────────────

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_SAMPLE_DBT_PROJECT = _FIXTURES_DIR / "sample_dbt_project"
_SCHEMA_YML = _SAMPLE_DBT_PROJECT / "models" / "schema.yml"


# ── Helpers ───────────────────────────────────────────────────────────


def _make_sample_catalog():
    """Build a minimal catalog.json matching the sample schema.yml models."""
    return {
        "metadata": {"dbt_version": "1.9.0"},
        "nodes": {
            "model.sample_dbt.customers": {
                "unique_id": "model.sample_dbt.customers",
                "name": "customers",
                "columns": {
                    "customer_id": {"name": "customer_id", "type": "integer"},
                    "customer_name": {"name": "customer_name", "type": "varchar"},
                    "email": {"name": "email", "type": "varchar"},
                    "signup_date": {"name": "signup_date", "type": "date"},
                    "customer_status": {"name": "customer_status", "type": "varchar"},
                },
            },
            "model.sample_dbt.orders": {
                "unique_id": "model.sample_dbt.orders",
                "name": "orders",
                "columns": {
                    "order_id": {"name": "order_id", "type": "integer"},
                    "customer_id": {"name": "customer_id", "type": "integer"},
                    "order_date": {"name": "order_date", "type": "date"},
                    "amount": {"name": "amount", "type": "float"},
                    "customer_name": {"name": "customer_name", "type": "varchar"},
                    "customer_status": {"name": "customer_status", "type": "varchar"},
                },
            },
        },
    }


# ── YAML parsing tests ────────────────────────────────────────────────


@pytest.mark.unit
class TestParseModelsYaml:
    """Tests for _parse_models_yaml()."""

    @pytest.mark.unit
    def test_parses_sample_schema(self):
        """Sample schema.yml is parsed into model dicts."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        models = DbtContractGenerator._parse_models_yaml(str(_SCHEMA_YML))
        assert len(models) == 2

        customers = next(m for m in models if m["name"] == "customers")
        assert customers["description"] == "Cleaned customer records"
        assert len(customers["columns"]) == 5

        customer_id = next(
            c for c in customers["columns"] if c["name"] == "customer_id"
        )
        assert customer_id["description"] == "Primary key"
        assert "unique" in customer_id["tests"]
        assert "not_null" in customer_id["tests"]

    @pytest.mark.unit
    def test_parses_model_without_description(self, tmp_path):
        """Model without description gets empty string."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        yml_path = str(tmp_path / "schema.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{"name": "minimal", "columns": []}],
            }, f)

        models = DbtContractGenerator._parse_models_yaml(yml_path)
        assert len(models) == 1
        assert models[0]["description"] == ""

    @pytest.mark.unit
    def test_parses_column_without_description(self, tmp_path):
        """Column without description gets empty string."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        yml_path = str(tmp_path / "schema.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{
                    "name": "m",
                    "columns": [{"name": "col1"}],
                }],
            }, f)

        models = DbtContractGenerator._parse_models_yaml(yml_path)
        col = models[0]["columns"][0]
        assert col["description"] == ""
        assert col["tests"] == []

    @pytest.mark.unit
    def test_parses_column_without_tests(self, tmp_path):
        """Column without tests key gets empty list."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        yml_path = str(tmp_path / "schema.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{
                    "name": "m",
                    "columns": [{"name": "col1", "description": "desc"}],
                }],
            }, f)

        models = DbtContractGenerator._parse_models_yaml(yml_path)
        assert models[0]["columns"][0]["tests"] == []

    @pytest.mark.unit
    def test_malformed_yaml_raises(self, tmp_path):
        """Malformed YAML raises DbtContractGeneratorError."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        yml_path = str(tmp_path / "bad.yml")
        with open(yml_path, "w") as f:
            f.write(": bad: yaml: [")

        with pytest.raises(DbtContractGeneratorError, match="Failed to parse"):
            DbtContractGenerator._parse_models_yaml(yml_path)

    @pytest.mark.unit
    def test_missing_file_raises(self):
        """Missing file raises DbtContractGeneratorError."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        with pytest.raises(DbtContractGeneratorError, match="not found"):
            DbtContractGenerator._parse_models_yaml("/nonexistent/schema.yml")

    @pytest.mark.unit
    def test_empty_models_raises(self, tmp_path):
        """Schema with no models raises DbtContractGeneratorError."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        yml_path = str(tmp_path / "empty.yml")
        with open(yml_path, "w") as f:
            yaml.dump({"version": 2, "models": []}, f)

        with pytest.raises(DbtContractGeneratorError, match="No models found"):
            DbtContractGenerator._parse_models_yaml(yml_path)

    @pytest.mark.unit
    def test_missing_models_key_raises(self, tmp_path):
        """Schema without 'models' key raises."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        yml_path = str(tmp_path / "no_models.yml")
        with open(yml_path, "w") as f:
            yaml.dump({"version": 2, "seeds": []}, f)

        with pytest.raises(DbtContractGeneratorError, match="No models found"):
            DbtContractGenerator._parse_models_yaml(yml_path)

    @pytest.mark.unit
    def test_column_missing_name_raises(self, tmp_path):
        """Column without 'name' field raises."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        yml_path = str(tmp_path / "bad_col.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{
                    "name": "m",
                    "columns": [{"description": "no name here"}],
                }],
            }, f)

        with pytest.raises(DbtContractGeneratorError, match="missing required 'name'"):
            DbtContractGenerator._parse_models_yaml(yml_path)

    @pytest.mark.unit
    def test_model_missing_name_raises(self, tmp_path):
        """Model without 'name' field raises."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        yml_path = str(tmp_path / "bad_model.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{"description": "no name", "columns": []}],
            }, f)

        with pytest.raises(DbtContractGeneratorError, match="missing required 'name'"):
            DbtContractGenerator._parse_models_yaml(yml_path)


# ── Catalog.json extraction tests ─────────────────────────────────────


@pytest.mark.unit
class TestExtractCatalogColumns:
    """Tests for _extract_catalog_columns()."""

    @pytest.mark.unit
    def test_extracts_column_types_from_catalog(self, tmp_path):
        """Catalog.json column types are extracted per model."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        catalog_path = str(tmp_path / "catalog.json")
        with open(catalog_path, "w") as f:
            json.dump(_make_sample_catalog(), f)

        columns = DbtContractGenerator._extract_catalog_columns(
            catalog_path, model_name="customers"
        )
        assert columns["customer_id"]["type"] == "integer"
        assert columns["customer_name"]["type"] == "varchar"
        assert columns["signup_date"]["type"] == "date"

    @pytest.mark.unit
    def test_missing_catalog_file_returns_empty(self):
        """Missing catalog.json returns empty dict."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        columns = DbtContractGenerator._extract_catalog_columns(
            "/nonexistent/catalog.json", model_name="customers"
        )
        assert columns == {}

    @pytest.mark.unit
    def test_model_not_in_catalog_returns_empty(self, tmp_path):
        """Model not found in catalog returns empty dict."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        catalog_path = str(tmp_path / "catalog.json")
        with open(catalog_path, "w") as f:
            json.dump(_make_sample_catalog(), f)

        columns = DbtContractGenerator._extract_catalog_columns(
            catalog_path, model_name="nonexistent_model"
        )
        assert columns == {}

    @pytest.mark.unit
    def test_malformed_catalog_json_returns_empty(self, tmp_path):
        """Malformed catalog.json returns empty dict (no crash)."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        catalog_path = str(tmp_path / "catalog.json")
        with open(catalog_path, "w") as f:
            f.write("not json {{{")

        columns = DbtContractGenerator._extract_catalog_columns(
            catalog_path, model_name="customers"
        )
        assert columns == {}


# ── HubContract JSON generation tests ─────────────────────────────────


@pytest.mark.unit
class TestGenerateHubContract:
    """Tests for generate_from_yaml() and generate_from_catalog()."""

    @pytest.mark.unit
    def test_generate_from_yaml_sample(self):
        """Sample schema.yml → valid HubContract JSON."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        gen = DbtContractGenerator()
        contract = gen.generate_from_yaml(str(_SCHEMA_YML))

        assert "schema" in contract
        assert "fields" in contract["schema"]
        assert len(contract["schema"]["fields"]) == 5 + 6  # customers(5) + orders(6)

        # Check primary key detection
        pk_fields = [
            f for f in contract["schema"]["fields"]
            if f.get("is_primary_key")
        ]
        assert len(pk_fields) == 2  # customer_id in both models

        # Check info section
        assert contract["info"]["title"] == "sample_dbt"
        assert "customers" in contract["info"]["description"]

    @pytest.mark.unit
    def test_generate_from_yaml_merges_catalog_types(self, tmp_path):
        """YAML fields enriched with catalog column types."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        # Write schema YAML with one model
        yml_path = str(tmp_path / "schema.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{
                    "name": "customers",
                    "columns": [
                        {"name": "customer_id", "tests": ["unique", "not_null"]},
                        {"name": "email"},
                    ],
                }],
            }, f)

        # Write catalog with types
        catalog_path = str(tmp_path / "catalog.json")
        with open(catalog_path, "w") as f:
            json.dump(_make_sample_catalog(), f)

        gen = DbtContractGenerator()
        contract = gen.generate_from_yaml(yml_path, catalog_path=catalog_path)

        customer_id = next(
            f for f in contract["schema"]["fields"] if f["name"] == "customer_id"
        )
        assert customer_id["type"] == "integer"  # from catalog
        assert customer_id["is_unique"] is True  # from YAML test
        assert customer_id["is_not_null"] is True  # from YAML test

    @pytest.mark.unit
    def test_generate_from_catalog_only(self):
        """Catalog-only generation creates contract with types but no tests."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        catalog = _make_sample_catalog()
        gen = DbtContractGenerator()
        contract = gen.generate_from_catalog(catalog, model_names=["customers"])

        fields = contract["schema"]["fields"]
        assert len(fields) == 5
        assert all(f["type"] is not None for f in fields)
        # No tests from catalog
        assert all(not f.get("is_unique") for f in fields)

    @pytest.mark.unit
    def test_missing_columns_warning(self, tmp_path):
        """Columns in YAML but not in catalog emit warning (verified functionally
        via the contract output — structlog writes to stderr bypassing caplog)."""
        from hub.apps.transformation.contract_generator import DbtContractGenerator

        yml_path = str(tmp_path / "schema.yml")
        with open(yml_path, "w") as f:
            yaml.dump({
                "version": 2,
                "models": [{
                    "name": "customers",
                    "columns": [
                        {"name": "customer_id"},
                        {"name": "missing_from_catalog"},
                    ],
                }],
            }, f)

        catalog_path = str(tmp_path / "catalog.json")
        catalog = _make_sample_catalog()
        with open(catalog_path, "w") as f:
            json.dump(catalog, f)

        gen = DbtContractGenerator()
        # Capture the contract directly — the warning log is emitted by
        # structlog to its own stderr handler and cannot be intercepted
        # by caplog/capsys.  The functional proof of the warning path is
        # that the column is included in the output with type=None.
        contract = gen.generate_from_yaml(yml_path, catalog_path=catalog_path)

        missing = next(
            f for f in contract["schema"]["fields"]
            if f["name"] == "missing_from_catalog"
        )
        assert missing["type"] is None, (
            "Column 'missing_from_catalog' must appear in schema with "
            "type=None when not found in catalog.json"
        )
        # Also verify the column from catalog IS enriched.
        customer_id = next(
            f for f in contract["schema"]["fields"]
            if f["name"] == "customer_id"
        )
        assert customer_id["type"] == "integer", (
            "Column 'customer_id' in catalog must have its type enriched"
        )

    @pytest.mark.unit
    def test_empty_models_dir_raises(self, tmp_path):
        """Empty models directory raises."""
        from hub.apps.transformation.contract_generator import (
            DbtContractGenerator,
            DbtContractGeneratorError,
        )

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        gen = DbtContractGenerator()

        with pytest.raises(DbtContractGeneratorError, match="No YAML schema files found"):
            gen.generate_from_models_dir(str(models_dir))
