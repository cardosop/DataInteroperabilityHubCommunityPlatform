"""
285.10.1.3 — Tests for ComplianceWarehouseSQLCompiler.
"""

import pytest

from hub.apps.compliance.warehouse_sql_compiler import ComplianceWarehouseSQLCompiler

# ── PII detection tests ────────────────────────────────────────────────


@pytest.mark.unit
class TestCompilePii:
    @pytest.mark.unit
    def test_pii_email_snowflake(self):
        checks = [{"type": "pii_email", "column": "contact"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 1
        assert result[0].check_type == "pii_email"
        assert "REGEXP_LIKE" in result[0].sql
        assert "contact" in result[0].sql
        assert "@" in result[0].sql  # email pattern includes @

    @pytest.mark.unit
    def test_pii_phone_snowflake(self):
        checks = [{"type": "pii_phone", "column": "phone"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "pii_phone"
        assert "REGEXP_LIKE" in result[0].sql
        # Phone pattern should look for digit sequences
        assert r"\d" in result[0].sql or "[0-9]" in result[0].sql

    @pytest.mark.unit
    def test_pii_ssn_snowflake(self):
        checks = [{"type": "pii_ssn", "column": "data"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "pii_ssn"
        assert "REGEXP_LIKE" in result[0].sql

    @pytest.mark.unit
    def test_pii_credit_card_snowflake(self):
        checks = [{"type": "pii_credit_card", "column": "payment"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "pii_credit_card"
        # Credit card pattern should look for 13-19 digit sequences
        assert r"\d" in result[0].sql

    @pytest.mark.unit
    def test_pii_ip_address_snowflake(self):
        checks = [{"type": "pii_ip_address", "column": "source_ip"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "pii_ip_address"
        assert "REGEXP_LIKE" in result[0].sql

    @pytest.mark.unit
    def test_pii_bigquery_regex(self):
        checks = [{"type": "pii_email", "column": "email_col"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "bigquery", "p.d.t")
        assert "REGEXP_CONTAINS" in result[0].sql

    @pytest.mark.unit
    def test_pii_databricks_regex(self):
        checks = [{"type": "pii_phone", "column": "tel"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "databricks", "c.s.t")
        assert "RLIKE" in result[0].sql


# ── Retention breach tests ────────────────────────────────────────────


@pytest.mark.unit
class TestCompileRetention:
    @pytest.mark.unit
    def test_retention_breach_snowflake(self):
        checks = [{"type": "retention_breach", "column": "created_at", "retention_days": 90}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "retention_breach"
        assert "DATEADD" in result[0].sql
        assert "90" in result[0].sql

    @pytest.mark.unit
    def test_retention_breach_bigquery(self):
        checks = [{"type": "retention_breach", "column": "ts", "retention_days": 365}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "bigquery", "p.d.t")
        assert "DATE_SUB" in result[0].sql
        assert "365" in result[0].sql

    @pytest.mark.unit
    def test_retention_breach_databricks(self):
        checks = [{"type": "retention_breach", "column": "dt", "retention_days": 30}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "databricks", "c.s.t")
        assert "INTERVAL" in result[0].sql

    @pytest.mark.unit
    def test_retention_default_days(self):
        checks = [{"type": "retention_breach", "column": "created_at"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        # Default retention is 90 days
        assert "90" in result[0].sql


# ── Classification mismatch tests ─────────────────────────────────────


@pytest.mark.unit
class TestCompileClassification:
    @pytest.mark.unit
    def test_classification_mismatch_snowflake(self):
        checks = [{"type": "classification_mismatch", "column": "col_type"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert result[0].check_type == "classification_mismatch"
        # Snowflake uses TYPEOF
        assert "TYPEOF" in result[0].sql

    @pytest.mark.unit
    def test_classification_mismatch_bigquery(self):
        checks = [{"type": "classification_mismatch", "column": "dtype"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "bigquery", "p.d.t")
        # BigQuery has no TYPEOF — uses SAFE_CAST with INT64 / FLOAT64
        assert result[0].check_type == "classification_mismatch"
        assert "SAFE_CAST" in result[0].sql
        assert "INT64" in result[0].sql
        assert "FLOAT64" in result[0].sql

    @pytest.mark.unit
    def test_classification_mismatch_databricks(self):
        checks = [{"type": "classification_mismatch", "column": "data_type"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "databricks", "c.s.t")
        assert result[0].check_type == "classification_mismatch"


# ── Multiple scans + regulations ─────────────────────────────────────


@pytest.mark.unit
class TestMultipleScans:
    @pytest.mark.unit
    def test_multiple_pii_checks(self):
        checks = [
            {"type": "pii_email", "column": "email"},
            {"type": "pii_phone", "column": "phone"},
            {"type": "pii_ssn", "column": "ssn"},
        ]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 3

    @pytest.mark.unit
    def test_regulations_param_passed(self):
        checks = [{"type": "pii_email", "column": "email"}]
        result = ComplianceWarehouseSQLCompiler.compile(
            checks,
            "snowflake",
            "DB.S.T",
            applicable_regulations=["GDPR", "CCPA"],
        )
        assert len(result) == 1
        # Both regulations MUST be reflected in the check name
        check_lower = result[0].check_name.lower()
        assert "gdpr" in check_lower, (
            f"Expected 'gdpr' in check name, got: {result[0].check_name}"
        )
        assert "ccpa" in check_lower, (
            f"Expected 'ccpa' in check name, got: {result[0].check_name}"
        )

    @pytest.mark.unit
    def test_unknown_type_skipped(self):
        checks = [{"type": "unknown_scan", "column": "x"}]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 0

    @pytest.mark.unit
    def test_mixed_known_and_unknown_types(self):
        """Unknown types are skipped while known types compile normally."""
        checks = [
            {"type": "pii_email", "column": "email"},
            {"type": "unknown_scan", "column": "x"},
            {"type": "pii_ssn", "column": "ssn"},
        ]
        result = ComplianceWarehouseSQLCompiler.compile(checks, "snowflake", "DB.S.T")
        assert len(result) == 2
        assert result[0].check_type == "pii_email"
        assert result[1].check_type == "pii_ssn"
