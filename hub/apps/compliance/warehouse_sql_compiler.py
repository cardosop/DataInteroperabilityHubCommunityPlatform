"""
285.10.1.3 — ComplianceWarehouseSQLCompiler: compile compliance scan
definitions into warehouse-specific SQL.

Covers three scan categories:

  - **PII detection**: email, phone, SSN, credit_card, ip_address
    using per-dialect regex functions
  - **Retention breach**: per-dialect DATE arithmetic
  - **Classification mismatch**: per-dialect TYPEOF equivalent

Reuses ``CompiledCheck`` from ``hub.apps.dq.warehouse_sql_compiler``.
"""

from __future__ import annotations

from typing import Any

from hub.apps.dq.warehouse_sql_compiler import CompiledCheck

# ── Per-dialect regex function templates ──────────────────────────────

_REGEX_FN: dict[str, str] = {
    "SNOWFLAKE": "REGEXP_LIKE({col}, '{pattern}')",
    "BIGQUERY": "REGEXP_CONTAINS({col}, r'{pattern}')",
    "DATABRICKS": "{col} RLIKE '{pattern}'",
}

# ── Per-dialect date function templates (for retention) ───────────────

_DATE_SUB_FN: dict[str, str] = {
    "SNOWFLAKE": "DATEADD(day, -{days}, CURRENT_DATE())",
    "BIGQUERY": "DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)",
    "DATABRICKS": "CURRENT_DATE() - INTERVAL {days} DAYS",
}

# ── Per-dialect TYPEOF equivalent ────────────────────────────────────

_TYPEOF_FN: dict[str, str] = {
    "SNOWFLAKE": "TYPEOF({col})",
    "BIGQUERY": (
        "CASE WHEN SAFE_CAST({col} AS INT64) = {col} THEN 'INT64' "
        "WHEN SAFE_CAST({col} AS FLOAT64) = {col} THEN 'FLOAT64' "
        "ELSE 'STRING' END"
    ),
    "DATABRICKS": "TYPEOF({col})",
}

# ── PII regex patterns ────────────────────────────────────────────────

_PII_PATTERNS: dict[str, str] = {
    "pii_email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "pii_phone": r"\+?\d[\d\s\(\)\-\.]{7,}\d",
    "pii_ssn": r"\d{3}-\d{2}-\d{4}",
    "pii_credit_card": r"\b(?:\d[ -]*?){13,19}\b",
    "pii_ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}

# ── Supported check types ─────────────────────────────────────────────

_SUPPORTED_CHECKS = {
    "pii_email",
    "pii_phone",
    "pii_ssn",
    "pii_credit_card",
    "pii_ip_address",
    "retention_breach",
    "classification_mismatch",
}


# ── 285.10.1.3.1 — ComplianceWarehouseSQLCompiler ────────────────────


class ComplianceWarehouseSQLCompiler:
    """Compile compliance scan definitions to per-warehouse SQL."""

    @staticmethod
    def compile(
        scan_definitions: list[dict[str, Any]],
        warehouse_type: str,
        table_fqn: str,
        applicable_regulations: list[str] | None = None,
    ) -> list[CompiledCheck]:
        """Compile scan definitions into ``CompiledCheck`` objects.

        Args:
            scan_definitions: List of dicts with ``type``, ``column``, and
                optional params.
            warehouse_type: ``snowflake``, ``bigquery``, or ``databricks``.
            table_fqn: Fully qualified table name.
            applicable_regulations: Optional list of regulation codes
                (e.g. ``["GDPR", "CCPA"]``) included in the check name.

        Returns:
            List of ``CompiledCheck`` (unknown types skipped).
        """
        wt = warehouse_type.upper()
        regs = applicable_regulations or []
        reg_suffix = "_" + "_".join(r.lower() for r in regs) if regs else ""
        compiled: list[CompiledCheck] = []

        for i, scan in enumerate(scan_definitions):
            scan_type = scan.get("type", "")
            if scan_type not in _SUPPORTED_CHECKS:
                continue

            column = scan.get("column", "")

            if scan_type.startswith("pii_"):
                result = _compile_pii(scan, scan_type, column, wt, table_fqn, i, reg_suffix)
            elif scan_type == "retention_breach":
                result = _compile_retention(scan, column, wt, table_fqn, i, reg_suffix)
            elif scan_type == "classification_mismatch":
                result = _compile_classification(column, wt, table_fqn, i, reg_suffix)
            else:
                continue

            if result:
                compiled.append(result)

        return compiled


# ── Per-scan compiler functions ───────────────────────────────────────


def _compile_pii(
    scan: dict[str, Any],
    scan_type: str,
    column: str,
    wt: str,
    table: str,
    idx: int,
    reg_suffix: str,
) -> CompiledCheck:
    pattern = _PII_PATTERNS.get(scan_type, ".*")
    regex_fn = _REGEX_FN.get(wt, _REGEX_FN["SNOWFLAKE"]).format(col=column, pattern=pattern)
    name = f"{scan_type}_{column}{reg_suffix}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type=scan_type,
        column_name=column,
        sql=(
            f"SELECT COUNT(*) AS match_count FROM {table} WHERE {column} IS NOT NULL AND {regex_fn}"
        ),
        result_key="match_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_retention(
    scan: dict[str, Any],
    column: str,
    wt: str,
    table: str,
    idx: int,
    reg_suffix: str,
) -> CompiledCheck:
    days = scan.get("retention_days", 90)
    date_fn = _DATE_SUB_FN.get(wt, _DATE_SUB_FN["SNOWFLAKE"]).format(days=days)
    name = f"retention_breach_{column}{reg_suffix}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="retention_breach",
        column_name=column,
        sql=(f"SELECT COUNT(*) AS stale_count FROM {table} WHERE {column} < {date_fn}"),
        result_key="stale_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_classification(
    column: str,
    wt: str,
    table: str,
    idx: int,
    reg_suffix: str,
) -> CompiledCheck:
    typeof_fn = _TYPEOF_FN.get(wt, _TYPEOF_FN["SNOWFLAKE"]).format(col=column)
    name = f"classification_mismatch_{column}{reg_suffix}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="classification_mismatch",
        column_name=column,
        sql=(
            f"SELECT {typeof_fn} AS actual_type, COUNT(*) AS cnt "
            f"FROM {table} WHERE {column} IS NOT NULL "
            f"GROUP BY 1"
        ),
        result_key="type_distribution",
        pass_condition="len(result) <= 1",
        warehouse_type=wt,
    )
