"""
285.9.2.2.1 — Tests for DbtModelScaffolder.

Tests SQL generation, YAML generation, dbt_project.yml stub,
nested type handling, and constraint mapping.
"""
import pytest

import yaml


# ── Sample HubContracts ───────────────────────────────────────────────


def _make_customers_contract():
    """Standard HubContract with constraints."""
    return {
        "schema": {
            "fields": [
                {
                    "name": "customer_id",
                    "data_type": "integer",
                    "description": "Primary key",
                    "is_primary_key": True,
                    "is_unique": True,
                    "nullable": False,
                },
                {
                    "name": "customer_name",
                    "data_type": "varchar",
                    "description": "Customer display name",
                },
                {
                    "name": "email",
                    "data_type": "varchar",
                    "description": "Email address",
                    "is_unique": True,
                },
                {
                    "name": "status",
                    "data_type": "varchar",
                    "description": "Account status",
                    "enum": ["ACTIVE", "INACTIVE", "PENDING"],
                },
            ],
            "primary_key": ["customer_id"],
        },
        "info": {
            "title": "customers",
            "description": "Cleaned customer records",
        },
    }


def _make_nested_contract():
    """Contract with STRUCT/nested type field."""
    return {
        "schema": {
            "fields": [
                {
                    "name": "id",
                    "data_type": "integer",
                    "is_primary_key": True,
                },
                {
                    "name": "metadata",
                    "data_type": "struct<key:varchar,value:varchar>",
                    "description": "Key-value metadata",
                },
            ],
            "primary_key": ["id"],
        },
        "info": {"title": "nested_model", "description": ""},
    }


# ── SQL generation tests ──────────────────────────────────────────────


@pytest.mark.unit
class TestGenerateSql:
    """Tests for _generate_sql()."""

    @pytest.mark.unit
    def test_generates_select_with_casts(self):
        """SQL SELECT with CAST for typed columns."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        sql = DbtModelScaffolder._generate_sql(contract, source_name="raw")

        assert "SELECT" in sql
        assert "FROM {{ source('raw', 'customers') }}" in sql
        # CAST for typed columns
        assert "CAST(source.customer_id AS integer)" in sql
        assert "CAST(source.customer_name AS varchar)" in sql
        # PK column aliased
        assert "AS customer_id" in sql

    @pytest.mark.unit
    def test_columns_without_type_skip_cast(self):
        """Columns missing data_type don't get CAST."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = {
            "schema": {
                "fields": [
                    {"name": "col1", "data_type": "varchar"},
                    {"name": "col2"},  # no type
                ],
                "primary_key": [],
            },
            "info": {"title": "test", "description": ""},
        }
        sql = DbtModelScaffolder._generate_sql(contract, source_name="raw")
        assert "CAST(source.col1 AS varchar)" in sql
        assert "CAST(source.col2" not in sql
        assert "source.col2" in sql  # bare column reference

    @pytest.mark.unit
    def test_nested_struct_type_cast(self):
        """STRUCT type gets CAST with full type signature."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_nested_contract()
        sql = DbtModelScaffolder._generate_sql(contract, source_name="raw")

        assert "CAST(source.metadata AS struct<key:varchar,value:varchar>)" in sql

    @pytest.mark.unit
    def test_default_source_name(self):
        """Default source name is 'raw'."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        sql = DbtModelScaffolder._generate_sql(contract)
        assert "{{ source('raw', 'customers') }}" in sql

    @pytest.mark.unit
    def test_custom_table_name(self):
        """Custom table name overrides contract title."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        sql = DbtModelScaffolder._generate_sql(
            contract, source_name="staging", table_name="cust"
        )
        assert "{{ source('staging', 'cust') }}" in sql

    @pytest.mark.unit
    def test_primary_key_column_comes_first(self):
        """PK columns are listed first in SELECT."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        sql = DbtModelScaffolder._generate_sql(contract, source_name="raw")
        # customer_id should appear before other columns
        pk_idx = sql.index("customer_id")
        name_idx = sql.index("customer_name")
        assert pk_idx < name_idx


# ── YAML generation tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestGenerateYaml:
    """Tests for _generate_yaml()."""

    @pytest.mark.unit
    def test_generates_model_yaml_with_tests(self):
        """YAML includes model name, description, columns with tests."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)

        assert data["version"] == 2
        assert len(data["models"]) == 1
        model = data["models"][0]
        assert model["name"] == "customers"
        assert model["description"] == "Cleaned customer records"

        columns = model["columns"]
        assert len(columns) == 4

        # PK column gets unique + not_null tests
        customer_id = next(c for c in columns if c["name"] == "customer_id")
        assert "unique" in customer_id["tests"]
        assert "not_null" in customer_id["tests"]

        # Unique column gets unique test
        email = next(c for c in columns if c["name"] == "email")
        assert "unique" in email["tests"]

        # Enum column gets accepted_values test
        status = next(c for c in columns if c["name"] == "status")
        assert any("accepted_values" in str(t) for t in status.get("tests", []))

    @pytest.mark.unit
    def test_enum_column_generates_accepted_values(self):
        """enum field generates accepted_values test with values."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)

        status = next(
            c for c in data["models"][0]["columns"] if c["name"] == "status"
        )
        # Should have an accepted_values test
        tests = status.get("tests", [])
        accepted = [t for t in tests if isinstance(t, dict) and "accepted_values" in t]
        assert len(accepted) == 1
        assert accepted[0]["accepted_values"]["values"] == ["ACTIVE", "INACTIVE", "PENDING"]

    @pytest.mark.unit
    def test_column_without_constraints_has_empty_tests(self):
        """Columns with no constraints get empty tests list."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = {
            "schema": {
                "fields": [{"name": "plain_col", "data_type": "varchar"}],
                "primary_key": [],
            },
            "info": {"title": "test", "description": ""},
        }
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)
        col = data["models"][0]["columns"][0]
        assert col["tests"] == []

    @pytest.mark.unit
    def test_column_description_preserved(self):
        """Field descriptions are written to YAML."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)

        email = next(
            c for c in data["models"][0]["columns"] if c["name"] == "email"
        )
        assert email["description"] == "Email address"

    @pytest.mark.unit
    def test_nullable_false_adds_not_null_test(self):
        """nullable: false generates not_null test."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)

        customer_id = next(
            c for c in data["models"][0]["columns"] if c["name"] == "customer_id"
        )
        assert "not_null" in customer_id["tests"]


# ── dbt_project.yml generation tests ──────────────────────────────────


@pytest.mark.unit
class TestGenerateProjectYml:
    """Tests for _generate_project_yml()."""

    @pytest.mark.unit
    def test_generates_minimal_project(self):
        """dbt_project.yml stub has required keys."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        yml_str = DbtModelScaffolder._generate_project_yml("my_project")
        data = yaml.safe_load(yml_str)

        assert data["name"] == "my_project"
        assert data["version"] == "1.0.0"
        assert data["profile"] == "meshant_dbt"
        assert "models" in data
        assert data["models"]["my_project"]["+materialized"] == "table"

    @pytest.mark.unit
    def test_custom_profile_name(self):
        """Custom profile name is used."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        yml_str = DbtModelScaffolder._generate_project_yml(
            "proj", profile="custom_profile"
        )
        data = yaml.safe_load(yml_str)
        assert data["profile"] == "custom_profile"

    @pytest.mark.unit
    def test_custom_materialization(self):
        """Custom materialization is used."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        yml_str = DbtModelScaffolder._generate_project_yml(
            "proj", materialized="view"
        )
        data = yaml.safe_load(yml_str)
        assert data["models"]["proj"]["+materialized"] == "view"


# ── Full scaffold generation tests ────────────────────────────────────


@pytest.mark.unit
class TestScaffoldAll:
    """Tests for scaffold_all()."""

    @pytest.mark.unit
    def test_scaffold_all_returns_three_files(self):
        """scaffold_all returns SQL + YAML + dbt_project.yml."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        scaffolder = DbtModelScaffolder()
        result = scaffolder.scaffold_all(
            contract=_make_customers_contract(),
            project_name="my_dbt_project",
            source_name="staging",
        )

        assert "model.sql" in result
        assert "model.yml" in result
        assert "dbt_project.yml" in result

        # SQL contains source reference
        assert "{{ source('staging', 'customers') }}" in result["model.sql"]
        # YAML is valid
        data = yaml.safe_load(result["model.yml"])
        assert data["models"][0]["name"] == "customers"
        # Project has correct name
        proj = yaml.safe_load(result["dbt_project.yml"])
        assert proj["name"] == "my_dbt_project"

    @pytest.mark.unit
    def test_scaffold_all_accepts_table_name(self):
        """table_name overrides the contract title for SQL generation."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        scaffolder = DbtModelScaffolder()
        result = scaffolder.scaffold_all(
            contract=_make_customers_contract(),
            project_name="p",
            table_name="raw_customers",
        )
        assert "{{ source('raw', 'raw_customers') }}" in result["model.sql"]

    @pytest.mark.unit
    def test_scaffold_prefixes_include_trailing_newline(self):
        """Generated SQL has proper formatting with trailing newline."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = _make_customers_contract()
        sql = DbtModelScaffolder._generate_sql(contract)
        assert sql.endswith("\n")


# ── Constraint edge case tests ────────────────────────────────────────


@pytest.mark.unit
class TestConstraintEdgeCases:
    """Edge cases for constraint mapping."""

    @pytest.mark.unit
    def test_all_constraints_on_single_column(self):
        """Column with unique + not_null + enum gets all tests."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = {
            "schema": {
                "fields": [{
                    "name": "code",
                    "data_type": "varchar",
                    "is_primary_key": True,
                    "is_unique": True,
                    "nullable": False,
                    "enum": ["A", "B", "C"],
                }],
                "primary_key": ["code"],
            },
            "info": {"title": "test", "description": ""},
        }
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)
        col = data["models"][0]["columns"][0]
        tests = col["tests"]
        # Has unique, not_null, accepted_values
        assert "unique" in tests
        assert "not_null" in tests
        assert any("accepted_values" in str(t) for t in tests)

    @pytest.mark.unit
    def test_field_uses_type_not_data_type(self):
        """Fields using 'type' key (from contract_generator) are handled."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = {
            "schema": {
                "fields": [
                    {"name": "id", "type": "integer", "is_primary_key": True},
                    {"name": "name", "type": "varchar"},
                ],
                "primary_key": ["id"],
            },
            "info": {"title": "test", "description": ""},
        }
        sql = DbtModelScaffolder._generate_sql(contract)
        assert "CAST(source.id AS integer)" in sql
        assert "CAST(source.name AS varchar)" in sql

    @pytest.mark.unit
    def test_field_uses_is_not_null_not_nullable(self):
        """Fields using is_not_null (from contract_generator) are handled."""
        from hub.apps.transformation.dbt_scaffolder import DbtModelScaffolder

        contract = {
            "schema": {
                "fields": [{
                    "name": "required_col",
                    "type": "varchar",
                    "is_not_null": True,
                }],
                "primary_key": [],
            },
            "info": {"title": "test", "description": ""},
        }
        yml_str = DbtModelScaffolder._generate_yaml(contract)
        data = yaml.safe_load(yml_str)
        col = data["models"][0]["columns"][0]
        assert "not_null" in col["tests"]
