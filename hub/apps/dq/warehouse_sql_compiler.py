"""
285.10.1.2 — DQWarehouseSQLCompiler: compile DQ check definitions into
warehouse-specific SQL for Snowflake, BigQuery, and Databricks.

Per-dialect functions for regex and date arithmetic:

  - Regex: Snowflake ``REGEXP_LIKE``, BigQuery ``REGEXP_CONTAINS``,
    Databricks ``RLIKE``
  - Date: Snowflake ``DATEADD``, BigQuery ``DATE_SUB``,
    Databricks ``INTERVAL``

Also provides ``ContractQualityRulesExtractor`` for extracting check
definitions from HubContract JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── 285.10.1.2.1 — CompiledCheck ─────────────────────────────────────


@dataclass
class CompiledCheck:
    """A single DQ check compiled to warehouse-specific SQL."""

    check_name: str
    check_type: str
    column_name: str
    sql: str
    result_key: str
    pass_condition: str
    warehouse_type: str = "SNOWFLAKE"


# ── Per-dialect function mappings ─────────────────────────────────────

_REGEX_FN: dict[str, str] = {
    "SNOWFLAKE": "REGEXP_LIKE({col}, '{pattern}')",
    "BIGQUERY": "REGEXP_CONTAINS({col}, r'{pattern}')",
    "DATABRICKS": "{col} RLIKE '{pattern}'",
}

_DATE_SUB_FN: dict[str, str] = {
    "SNOWFLAKE": "DATEADD(hour, -{hours}, CURRENT_TIMESTAMP())",
    "BIGQUERY": "DATE_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)",
    "DATABRICKS": "CURRENT_TIMESTAMP() - INTERVAL {hours} HOURS",
}


# ── 285.10.1.2.1 — DQWarehouseSQLCompiler ─────────────────────────────


class DQWarehouseSQLCompiler:
    """Compile DQ check definitions to per-warehouse SQL."""

    _SUPPORTED_CHECKS = {
        "not_null",
        "unique",
        "accepted_values",
        "range",
        "regex",
        "freshness",
        "row_count",
        "column_stats",
    }

    @staticmethod
    def compile(
        check_definitions: list[dict[str, Any]],
        warehouse_type: str,
        table_fqn: str,
    ) -> list[CompiledCheck]:
        """Compile a list of check definitions into ``CompiledCheck``
        objects with warehouse-specific SQL.

        Args:
            check_definitions: List of dicts with ``type``, ``column``,
                and optional params.
            warehouse_type: ``snowflake``, ``bigquery``, or ``databricks``.
            table_fqn: Fully qualified table name.

        Returns:
            List of ``CompiledCheck`` (unknown check types skipped).
        """
        wt = warehouse_type.upper()
        compiled: list[CompiledCheck] = []

        for i, check in enumerate(check_definitions):
            check_type = check.get("type", "")
            if check_type not in DQWarehouseSQLCompiler._SUPPORTED_CHECKS:
                continue

            check.get("column", "")
            compiler_fn = _CHECK_COMPILERS.get(check_type)
            if compiler_fn is None:
                continue

            result = compiler_fn(check, wt, table_fqn, i)
            if result:
                compiled.append(result)

        return compiled


# ── Per-check compiler functions ──────────────────────────────────────


def _compile_not_null(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    name = f"not_null_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="not_null",
        column_name=col,
        sql=f"SELECT COUNT(*) AS null_count FROM {table} WHERE {col} IS NULL",
        result_key="null_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_unique(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    name = f"unique_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="unique",
        column_name=col,
        sql=(
            f"SELECT {col}, COUNT(*) AS dup_count FROM {table} GROUP BY {col} HAVING COUNT(*) > 1"
        ),
        result_key="dup_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_accepted_values(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    values = check.get("values", [])
    quoted = ", ".join(f"'{v}'" for v in values)
    name = f"accepted_values_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="accepted_values",
        column_name=col,
        sql=(
            f"SELECT COUNT(*) AS invalid_count FROM {table} "
            f"WHERE {col} IS NOT NULL AND {col} NOT IN ({quoted})"
        ),
        result_key="invalid_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_range(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    conditions: list[str] = []
    if "min" in check:
        conditions.append(f"{col} < {check['min']}")
    if "max" in check:
        conditions.append(f"{col} > {check['max']}")

    name = f"range_{col}_{idx}"
    where = " OR ".join(conditions) if conditions else "1=0"
    return CompiledCheck(
        check_name=name,
        check_type="range",
        column_name=col,
        sql=f"SELECT COUNT(*) AS out_of_range FROM {table} WHERE {where}",
        result_key="out_of_range",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_regex(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    pattern = check.get("pattern", ".*")
    regex_fn = _REGEX_FN.get(wt, _REGEX_FN["SNOWFLAKE"]).format(col=col, pattern=pattern)
    name = f"regex_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="regex",
        column_name=col,
        sql=(
            f"SELECT COUNT(*) AS regex_fail FROM {table} WHERE {col} IS NOT NULL AND NOT {regex_fn}"
        ),
        result_key="regex_fail",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_freshness(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check.get("column", "updated_at")
    hours = check.get("max_age_hours", 24)
    date_fn = _DATE_SUB_FN.get(wt, _DATE_SUB_FN["SNOWFLAKE"]).format(hours=hours)
    name = f"freshness_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="freshness",
        column_name=col,
        sql=(f"SELECT COUNT(*) AS stale_count FROM {table} WHERE {col} < {date_fn}"),
        result_key="stale_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_row_count(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    min_rows = check.get("min", 0)
    max_rows = check.get("max")
    name = f"row_count_{idx}"
    conditions = [f"cnt < {min_rows}"]
    if max_rows is not None:
        conditions.append(f"cnt > {max_rows}")
    where = " OR ".join(conditions)
    return CompiledCheck(
        check_name=name,
        check_type="row_count",
        column_name="",
        sql=(
            f"WITH _rc AS (SELECT COUNT(*) AS cnt FROM {table}) SELECT cnt FROM _rc WHERE {where}"
        ),
        result_key="row_count",
        pass_condition="result == 0",
        warehouse_type=wt,
    )


def _compile_column_stats(check: dict[str, Any], wt: str, table: str, idx: int) -> CompiledCheck:
    col = check["column"]
    name = f"column_stats_{col}_{idx}"
    return CompiledCheck(
        check_name=name,
        check_type="column_stats",
        column_name=col,
        sql=(
            f"SELECT COUNT(*) AS cnt, MIN({col}) AS min_val, "
            f"MAX({col}) AS max_val, AVG({col}) AS avg_val "
            f"FROM {table} WHERE {col} IS NOT NULL"
        ),
        result_key="stats",
        pass_condition="result is not None",
        warehouse_type=wt,
    )


# Registry of check compilers
_CHECK_COMPILERS: dict[str, Any] = {
    "not_null": _compile_not_null,
    "unique": _compile_unique,
    "accepted_values": _compile_accepted_values,
    "range": _compile_range,
    "regex": _compile_regex,
    "freshness": _compile_freshness,
    "row_count": _compile_row_count,
    "column_stats": _compile_column_stats,
}


# ── 285.10.1.2.2 — ContractQualityRulesExtractor ─────────────────────


class ContractQualityRulesExtractor:
    """Extract DQ check definitions from HubContract JSON."""

    @staticmethod
    def get_warehouse_check_definitions(
        contract: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract check definitions consumable by ``DQWarehouseSQLCompiler``.

        Sources:
          - ``schema.fields[]`` — ``is_not_null`` → not_null check,
            ``is_unique`` → unique check, ``enum`` → accepted_values check
          - ``quality.rules[]`` → type + column + params dicts
        """
        checks: list[dict[str, Any]] = []

        if not isinstance(contract, dict):
            return checks

        # From schema fields
        schema = contract.get("schema", {})
        if isinstance(schema, dict):
            fields = schema.get("fields", [])
            if isinstance(fields, list):
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    col = f.get("name", "")
                    if not col:
                        continue
                    if f.get("is_not_null"):
                        checks.append({"type": "not_null", "column": col})
                    if f.get("is_unique"):
                        checks.append({"type": "unique", "column": col})
                    enum_vals = f.get("enum")
                    if enum_vals and isinstance(enum_vals, list):
                        checks.append(
                            {
                                "type": "accepted_values",
                                "column": col,
                                "values": enum_vals,
                            }
                        )

        # From quality rules
        quality = contract.get("quality", {})
        if isinstance(quality, dict):
            rules = quality.get("rules", [])
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    rule_type = rule.get("type", "")
                    if not rule_type:
                        continue
                    col = rule.get("column", "")
                    params = rule.get("params", {}) or {}
                    entry: dict[str, Any] = {"type": rule_type}
                    if col:
                        entry["column"] = col
                    entry.update(params)
                    checks.append(entry)

        return checks
