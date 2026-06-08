"""
285.10.1.2 — Tests for DQWarehouseSQLCompiler and ContractQualityRulesExtractor.
"""
import pytest

from hub.apps.dq.warehouse_sql_compiler import (
    CompiledCheck,
    DQWarehouseSQLCompiler,
    ContractQualityRulesExtractor,
)


# ── CompiledCheck tests ───────────────────────────────────────────────


@pytest.mark.unit
class TestCompiledCheck:
    @pytest.mark.unit
    def test_dataclass_fields(self):
        c = CompiledCheck(
            check_name="not_null_customers_email",
            check_type="not_null",
            column_name="email",
            sql="SELECT COUNT(*) FROM t WHERE email IS NULL",
            result_key="null_count",
            pass_condition="result == 0",
            warehouse_type="SNOWFLAKE",
        )
        assert c.check_name == "not_null_customers_email"
        assert c.column_name == "email"
        assert c.warehouse_type == "SNOWFLAKE"


# ── DQWarehouseSQLCompiler — not_null ─────────────────────────────────


@pytest.mark.unit
class TestCompileNotNull:
    @pytest.mark.unit
    def test_snowflake_not_null(self):
        checks = [{"type": "not_null", "column": "email"}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.SCHEMA.CUSTOMERS")
        assert len(result) == 1
        assert result[0].check_type == "not_null"
        assert "email IS NULL" in result[0].sql
        assert "DB.SCHEMA.CUSTOMERS" in result[0].sql
        assert result[0].warehouse_type == "SNOWFLAKE"

    @pytest.mark.unit
    def test_bigquery_not_null(self):
        checks = [{"type": "not_null", "column": "customer_id"}]
        result = DQWarehouseSQLCompiler.compile(checks, "bigquery", "proj.ds.tbl")
        assert result[0].warehouse_type == "BIGQUERY"
        assert "customer_id IS NULL" in result[0].sql

    @pytest.mark.unit
    def test_databricks_not_null(self):
        checks = [{"type": "not_null", "column": "name"}]
        result = DQWarehouseSQLCompiler.compile(checks, "databricks", "cat.sch.tbl")
        assert result[0].warehouse_type == "DATABRICKS"


# ── DQWarehouseSQLCompiler — unique ───────────────────────────────────


@pytest.mark.unit
class TestCompileUnique:
    @pytest.mark.unit
    def test_unique_check(self):
        checks = [{"type": "unique", "column": "customer_id"}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "unique"
        assert "COUNT(DISTINCT" in result[0].sql or "COUNT(*)" in result[0].sql
        assert "HAVING" in result[0].sql


# ── DQWarehouseSQLCompiler — accepted_values ──────────────────────────


@pytest.mark.unit
class TestCompileAcceptedValues:
    @pytest.mark.unit
    def test_accepted_values_check(self):
        checks = [{"type": "accepted_values", "column": "status", "values": ["ACTIVE", "INACTIVE", "PENDING"]}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "accepted_values"
        assert "NOT IN" in result[0].sql
        assert "ACTIVE" in result[0].sql


# ── DQWarehouseSQLCompiler — range ────────────────────────────────────


@pytest.mark.unit
class TestCompileRange:
    @pytest.mark.unit
    def test_range_check_min_max(self):
        checks = [{"type": "range", "column": "age", "min": 0, "max": 120}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "range"
        assert "age < 0" in result[0].sql or "age > 120" in result[0].sql

    @pytest.mark.unit
    def test_range_min_only(self):
        checks = [{"type": "range", "column": "score", "min": 0}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "range"


# ── DQWarehouseSQLCompiler — regex ────────────────────────────────────


@pytest.mark.unit
class TestCompileRegex:
    @pytest.mark.unit
    def test_snowflake_regex(self):
        checks = [{"type": "regex", "column": "email", "pattern": r"^[a-z]+@.*"}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert "REGEXP_LIKE" in result[0].sql

    @pytest.mark.unit
    def test_bigquery_regex(self):
        checks = [{"type": "regex", "column": "phone", "pattern": r"^\d{10}$"}]
        result = DQWarehouseSQLCompiler.compile(checks, "bigquery", "p.d.t")
        assert "REGEXP_CONTAINS" in result[0].sql

    @pytest.mark.unit
    def test_databricks_regex(self):
        checks = [{"type": "regex", "column": "code", "pattern": r"^[A-Z]{3}$"}]
        result = DQWarehouseSQLCompiler.compile(checks, "databricks", "c.s.t")
        assert "RLIKE" in result[0].sql


# ── DQWarehouseSQLCompiler — freshness ────────────────────────────────


@pytest.mark.unit
class TestCompileFreshness:
    @pytest.mark.unit
    def test_snowflake_freshness(self):
        checks = [{"type": "freshness", "column": "updated_at", "max_age_hours": 24}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "freshness"
        assert "DATEADD" in result[0].sql

    @pytest.mark.unit
    def test_bigquery_freshness(self):
        checks = [{"type": "freshness", "column": "ts", "max_age_hours": 1}]
        result = DQWarehouseSQLCompiler.compile(checks, "bigquery", "p.d.t")
        assert "DATE_SUB" in result[0].sql

    @pytest.mark.unit
    def test_databricks_freshness(self):
        checks = [{"type": "freshness", "column": "dt", "max_age_hours": 6}]
        result = DQWarehouseSQLCompiler.compile(checks, "databricks", "c.s.t")
        assert "INTERVAL" in result[0].sql


# ── DQWarehouseSQLCompiler — row_count ────────────────────────────────


@pytest.mark.unit
class TestCompileRowCount:
    @pytest.mark.unit
    def test_row_count_min(self):
        checks = [{"type": "row_count", "min": 100}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "row_count"
        assert "COUNT(*)" in result[0].sql


# ── DQWarehouseSQLCompiler — column_stats ─────────────────────────────


@pytest.mark.unit
class TestCompileColumnStats:
    @pytest.mark.unit
    def test_column_stats(self):
        checks = [{"type": "column_stats", "column": "amount"}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "column_stats"
        assert "MIN" in result[0].sql
        assert "MAX" in result[0].sql
        assert "AVG" in result[0].sql


# ── DQWarehouseSQLCompiler — multiple checks ──────────────────────────


@pytest.mark.unit
class TestCompileMultipleChecks:
    @pytest.mark.unit
    def test_multiple_checks(self):
        checks = [
            {"type": "not_null", "column": "id"},
            {"type": "unique", "column": "email"},
            {"type": "range", "column": "age", "min": 0, "max": 150},
        ]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 3
        assert result[0].check_type == "not_null"
        assert result[1].check_type == "unique"
        assert result[2].check_type == "range"


@pytest.mark.unit
class TestUnknownCheckType:
    @pytest.mark.unit
    def test_unknown_type_skipped(self):
        checks = [{"type": "unknown_future_check", "column": "x"}]
        result = DQWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 0  # unknown types skipped gracefully


# ── ContractQualityRulesExtractor tests ───────────────────────────────


@pytest.mark.unit
class TestContractQualityRulesExtractor:
    @pytest.mark.unit
    def test_extract_from_hub_contract(self):
        contract = {
            "schema": {
                "fields": [
                    {"name": "id", "is_not_null": True, "is_unique": True},
                    {"name": "email", "is_not_null": True},
                    {"name": "status", "enum": ["ACTIVE", "INACTIVE"]},
                ]
            },
            "quality": {
                "rules": [
                    {"type": "freshness", "column": "updated_at", "params": {"max_age_hours": 24}},
                    {"type": "row_count", "params": {"min": 1}},
                ]
            },
        }
        checks = ContractQualityRulesExtractor.get_warehouse_check_definitions(contract)
        assert len(checks) >= 5  # not_null(id), unique(id), not_null(email), accepted_values(status), freshness, row_count

        not_null_checks = [c for c in checks if c["type"] == "not_null"]
        assert len(not_null_checks) >= 2

        unique_checks = [c for c in checks if c["type"] == "unique"]
        assert len(unique_checks) >= 1

    @pytest.mark.unit
    def test_extract_empty_contract(self):
        contract = {"schema": {"fields": []}}
        checks = ContractQualityRulesExtractor.get_warehouse_check_definitions(contract)
        assert checks == []

    @pytest.mark.unit
    def test_extract_handles_missing_sections(self):
        checks = ContractQualityRulesExtractor.get_warehouse_check_definitions({})
        assert checks == []
