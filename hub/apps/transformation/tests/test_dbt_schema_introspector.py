"""
285.9.3.1 — Tests for DbtSchemaIntrospector.

Tests SQL generation and result normalization for Snowflake/BQ/Databricks.
"""
import pytest

from hub.apps.transformation.dbt_schema_introspector import DbtSchemaIntrospector


@pytest.mark.unit
class TestSqlGeneration:
    """Tests for _build_*_query()."""

    @pytest.mark.unit
    def test_snowflake_query(self):
        """Snowflake INFORMATION_SCHEMA query is correct."""
        sql = DbtSchemaIntrospector._build_snowflake_query("analytics", "customers")
        assert "INFORMATION_SCHEMA.COLUMNS" in sql
        assert "analytics" in sql
        assert "customers" in sql
        assert "column_name" in sql
        assert "data_type" in sql

    @pytest.mark.unit
    def test_bigquery_query(self):
        """BigQuery INFORMATION_SCHEMA query is correct."""
        sql = DbtSchemaIntrospector._build_bigquery_query(
            "my-project", "analytics", "customers"
        )
        assert "INFORMATION_SCHEMA.COLUMNS" in sql
        assert "my-project.analytics" in sql
        assert "customers" in sql
        assert "column_name" in sql
        assert "data_type" in sql

    @pytest.mark.unit
    def test_databricks_query(self):
        """Databricks DESCRIBE TABLE query is correct."""
        sql = DbtSchemaIntrospector._build_databricks_query(
            "main", "dbt_schema", "customers"
        )
        assert "DESCRIBE TABLE" in sql
        assert "main.dbt_schema.customers" in sql


@pytest.mark.unit
class TestNormalization:
    """Tests for _normalize_*_result()."""

    @pytest.mark.unit
    def test_normalize_snowflake_result(self):
        """Snowflake rows normalize to {fields: [{name, data_type, nullable}]}."""
        rows = [
            ("customer_id", "NUMBER(38,0)", "NO"),
            ("customer_name", "VARCHAR(255)", "YES"),
            ("email", "VARCHAR(255)", "YES"),
            ("signup_date", "DATE", "NO"),
            ("status", "VARCHAR(50)", "NO"),
        ]
        schema = DbtSchemaIntrospector._normalize_snowflake_result(rows)
        assert "fields" in schema
        fields = schema["fields"]
        assert len(fields) == 5

        # customer_id: NUMBER → numeric, not null
        pk = next(f for f in fields if f["name"] == "customer_id")
        assert pk["data_type"] == "numeric"
        assert pk["nullable"] is False

        # customer_name: VARCHAR → varchar, nullable
        name = next(f for f in fields if f["name"] == "customer_name")
        assert name["data_type"] == "varchar"
        assert name["nullable"] is True

    @pytest.mark.unit
    def test_normalize_bigquery_result(self):
        """BigQuery rows normalize to {fields: [{name, data_type, nullable}]}."""
        rows = [
            ("customer_id", "INT64", "NO"),
            ("customer_name", "STRING", "YES"),
            ("amount", "FLOAT64", "YES"),
            ("created_at", "TIMESTAMP", "NO"),
            ("data", "BYTES", "YES"),
        ]
        schema = DbtSchemaIntrospector._normalize_bigquery_result(rows)
        fields = schema["fields"]
        assert len(fields) == 5

        assert next(f for f in fields if f["name"] == "customer_id")["data_type"] == "integer"
        assert next(f for f in fields if f["name"] == "customer_name")["data_type"] == "varchar"
        assert next(f for f in fields if f["name"] == "amount")["data_type"] == "float"
        assert next(f for f in fields if f["name"] == "created_at")["data_type"] == "timestamp"
        assert next(f for f in fields if f["name"] == "data")["data_type"] == "bytes"

    @pytest.mark.unit
    def test_normalize_databricks_result(self):
        """Databricks DESCRIBE TABLE rows normalize correctly."""
        rows = [
            ("customer_id", "int", None),
            ("customer_name", "string", None),
            ("amount", "decimal(18,2)", None),
            ("is_active", "boolean", None),
            ("created_date", "date", None),
            ("metadata", "struct<key:string,value:string>", None),
        ]
        schema = DbtSchemaIntrospector._normalize_databricks_result(rows)
        fields = schema["fields"]
        assert len(fields) == 6

        assert next(f for f in fields if f["name"] == "customer_id")["data_type"] == "integer"
        assert next(f for f in fields if f["name"] == "customer_name")["data_type"] == "varchar"
        assert next(f for f in fields if f["name"] == "amount")["data_type"] == "decimal"
        assert next(f for f in fields if f["name"] == "is_active")["data_type"] == "boolean"
        assert next(f for f in fields if f["name"] == "created_date")["data_type"] == "date"
        assert next(f for f in fields if f["name"] == "metadata")["data_type"] == "struct"

    @pytest.mark.unit
    def test_normalize_databricks_nullable_detection(self):
        """Databricks DESCRIBE infers nullability from third column or defaults."""
        # Databricks doesn't always return nullable info in DESCRIBE TABLE.
        # When the third column is None, default to nullable=True.
        rows = [("col1", "int", None), ("col2", "string", None)]
        schema = DbtSchemaIntrospector._normalize_databricks_result(rows)
        fields = schema["fields"]
        assert all(f["nullable"] is True for f in fields)

    @pytest.mark.unit
    def test_empty_result_returns_empty_fields(self):
        """Empty row set returns {fields: []}."""
        for normalizer in [
            DbtSchemaIntrospector._normalize_snowflake_result,
            DbtSchemaIntrospector._normalize_bigquery_result,
            DbtSchemaIntrospector._normalize_databricks_result,
        ]:
            schema = normalizer([])
            assert schema == {"fields": []}


@pytest.mark.unit
class TestIntrospectMethod:
    """Tests for introspect() public method."""

    @pytest.mark.unit
    def test_introspect_returns_normalized_schema(self):
        """introspect() accepts any warehouse type and returns normalized schema."""

        class FakeCursor:
            def execute(self, sql, params=None):
                pass

            def fetchall(self):
                return [
                    ("id", "NUMBER(38,0)", "NO"),
                    ("name", "VARCHAR(255)", "YES"),
                ]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        class FakeConn:
            def cursor(self):
                return FakeCursor()

        result = DbtSchemaIntrospector.introspect(
            connection=FakeConn(),
            warehouse_type="snowflake",
            database="analytics",
            schema_name="public",
            table_name="output_table",
        )
        assert result["fields"][0]["name"] == "id"
        assert result["fields"][0]["data_type"] == "numeric"
