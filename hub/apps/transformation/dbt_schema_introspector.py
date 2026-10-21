"""
285.9.3.1 — DbtSchemaIntrospector: query warehouse INFORMATION_SCHEMA.

Queries Snowflake, BigQuery, or Databricks INFORMATION_SCHEMA (or
DESCRIBE TABLE) for the output table schema and normalizes the result
to ``{fields: [{name, data_type, nullable}]}`` — the format expected
by ``SchemaCompareService.compare()``.
"""

from __future__ import annotations

import re
from typing import Any


class DbtSchemaIntrospector:
    """Query a customer warehouse for a table's column schema and return
    a normalized representation suitable for schema comparison.

    Does NOT manage connections — the caller must supply a PEP 249
    cursor or connection.  This keeps the class warehouse-driver-agnostic.
    """

    # ── Public API ────────────────────────────────────────────────────

    @staticmethod
    def introspect(
        *,
        connection: Any,
        warehouse_type: str,
        database: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> dict[str, Any]:
        """Query the warehouse and return normalized schema.

        Args:
            connection: A PEP 249 connection (or any object with a
                ``cursor()`` method that returns a context-manager
                cursor).
            warehouse_type: ``"snowflake"``, ``"bigquery"``, or
                ``"databricks"``.
            database: Snowflake database / BQ project / Databricks catalog.
            schema_name: Schema / dataset name.
            table_name: Target table name.

        Returns:
            ``{"fields": [{"name": str, "data_type": str, "nullable": bool}]}``
        """
        wtype = warehouse_type.lower()

        if wtype == "snowflake":
            sql = DbtSchemaIntrospector._build_snowflake_query(database, table_name, schema_name)
            normalizer = DbtSchemaIntrospector._normalize_snowflake_result
        elif wtype == "bigquery":
            sql = DbtSchemaIntrospector._build_bigquery_query(database, schema_name, table_name)
            normalizer = DbtSchemaIntrospector._normalize_bigquery_result
        elif wtype == "databricks":
            sql = DbtSchemaIntrospector._build_databricks_query(database, schema_name, table_name)
            normalizer = DbtSchemaIntrospector._normalize_databricks_result
        else:
            raise ValueError(
                f"Unsupported warehouse type: '{warehouse_type}'. "
                "Expected snowflake, bigquery, or databricks."
            )

        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        return normalizer(rows)

    # ── SQL builders ──────────────────────────────────────────────────

    @staticmethod
    def _build_snowflake_query(database: str, table_name: str, schema_name: str = "") -> str:
        schema_filter = f"AND table_schema = '{schema_name}'" if schema_name else ""
        return (
            f"SELECT column_name, data_type, is_nullable "
            f"FROM {database}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = '{table_name}' {schema_filter}"
        )

    @staticmethod
    def _build_bigquery_query(project: str, dataset: str, table_name: str) -> str:
        return (
            f"SELECT column_name, data_type, is_nullable "
            f"FROM {project}.{dataset}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = '{table_name}'"
        )

    @staticmethod
    def _build_databricks_query(catalog: str, schema_name: str, table_name: str) -> str:
        return f"DESCRIBE TABLE {catalog}.{schema_name}.{table_name}"

    # ── Normalizers ───────────────────────────────────────────────────

    @staticmethod
    def _normalize_snowflake_result(
        rows: list[tuple[str, str, str]],
    ) -> dict[str, Any]:
        """Normalize Snowflake INFORMATION_SCHEMA.COLUMNS output."""
        fields: list[dict[str, Any]] = []
        for col_name, data_type, is_nullable in rows:
            fields.append(
                {
                    "name": col_name,
                    "data_type": _SF_TYPE_MAP.get(_extract_base_type(data_type), data_type.lower()),
                    "nullable": is_nullable.upper() == "YES",
                }
            )
        return {"fields": fields}

    @staticmethod
    def _normalize_bigquery_result(
        rows: list[tuple[str, str, str]],
    ) -> dict[str, Any]:
        """Normalize BigQuery INFORMATION_SCHEMA.COLUMNS output."""
        fields: list[dict[str, Any]] = []
        for col_name, data_type, is_nullable in rows:
            fields.append(
                {
                    "name": col_name,
                    "data_type": _BQ_TYPE_MAP.get(data_type.lower(), data_type.lower()),
                    "nullable": is_nullable.upper() == "YES",
                }
            )
        return {"fields": fields}

    @staticmethod
    def _normalize_databricks_result(
        rows: list[tuple[str, str, Any]],
    ) -> dict[str, Any]:
        """Normalize Databricks DESCRIBE TABLE output.

        Databricks ``DESCRIBE TABLE`` returns:
        ``(col_name, data_type, comment)`` — the third column is a
        comment string, NOT a nullable flag.  We default all columns
        to ``nullable: True`` since Databricks doesn't expose
        nullability through DESCRIBE TABLE.
        """
        fields: list[dict[str, Any]] = []
        for row in rows:
            col_name = row[0]
            data_type = row[1] if len(row) > 1 else "unknown"
            fields.append(
                {
                    "name": col_name,
                    "data_type": _DBR_TYPE_MAP.get(
                        _extract_base_type(data_type), data_type.lower()
                    ),
                    "nullable": True,
                }
            )
        return {"fields": fields}

    # ── Contract validation (285.9.3.2) ───────────────────────────────

    @staticmethod
    def validate_against_contract(
        introspected: dict[str, Any],
        contract_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare introspected warehouse schema against a HubContract's
        expected fields.

        Args:
            introspected: ``{"fields": [...]}`` from ``introspect()``.
            contract_fields: List of field dicts from HubContract, each
                with ``name``, ``data_type``, and optionally ``nullable``.

        Returns:
            ``{"match": bool, "added": [...], "removed": [...], "changed": [...]}``
            where each entry in the diff lists is a field dict.
        """
        actual = {f["name"]: f for f in introspected.get("fields", [])}
        expected = {f["name"]: f for f in contract_fields}

        actual_names = set(actual.keys())
        expected_names = set(expected.keys())

        added = [
            {"name": n, "data_type": actual[n]["data_type"]}
            for n in sorted(actual_names - expected_names)
        ]
        removed = [
            {"name": n, "data_type": expected[n].get("data_type", "unknown")}
            for n in sorted(expected_names - actual_names)
        ]
        changed = []
        for n in sorted(actual_names & expected_names):
            a_type = actual[n].get("data_type", "").lower()
            e_type = expected[n].get("data_type", "").lower()
            a_nullable = actual[n].get("nullable")
            e_nullable = expected[n].get("nullable")
            if a_type != e_type or (e_nullable is not None and a_nullable != e_nullable):
                changed.append(
                    {
                        "name": n,
                        "expected_type": e_type,
                        "actual_type": a_type,
                        "expected_nullable": e_nullable,
                        "actual_nullable": a_nullable,
                    }
                )

        return {
            "match": not (added or removed or changed),
            "added": added,
            "removed": removed,
            "changed": changed,
        }


# ── Type normalisation maps ───────────────────────────────────────────


def _extract_base_type(raw_type: str) -> str:
    """Strip length/precision from a type string.

    >>> _extract_base_type("VARCHAR(255)")
    'varchar'
    >>> _extract_base_type("NUMBER(38,0)")
    'number'
    """
    match = re.match(r"([a-zA-Z_]+)", raw_type)
    return match.group(1).lower() if match else raw_type.lower()


# Snowflake → canonical type
_SF_TYPE_MAP: dict[str, str] = {
    "number": "numeric",
    "numeric": "numeric",
    "decimal": "decimal",
    "integer": "integer",
    "int": "integer",
    "varchar": "varchar",
    "char": "varchar",
    "character": "varchar",
    "string": "varchar",
    "text": "varchar",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "timestamp_ntz": "timestamp",
    "timestamp_ltz": "timestamp",
    "timestamp_tz": "timestamp",
    "time": "time",
    "float": "float",
    "float4": "float",
    "float8": "float",
    "double": "float",
    "real": "float",
    "binary": "bytes",
    "variant": "variant",
    "object": "object",
    "array": "array",
    "geography": "geography",
    "geometry": "geometry",
}

# BigQuery → canonical type
_BQ_TYPE_MAP: dict[str, str] = {
    "int64": "integer",
    "integer": "integer",
    "numeric": "numeric",
    "bignumeric": "decimal",
    "float64": "float",
    "string": "varchar",
    "bytes": "bytes",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "time": "time",
    "struct": "struct",
    "array": "array",
    "geography": "geography",
    "json": "variant",
    "interval": "interval",
}

# Databricks → canonical type
_DBR_TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "integer": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "tinyint": "integer",
    "decimal": "decimal",
    "numeric": "numeric",
    "double": "float",
    "float": "float",
    "real": "float",
    "string": "varchar",
    "varchar": "varchar",
    "char": "varchar",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "timestamp": "timestamp",
    "timestamp_ntz": "timestamp",
    "binary": "bytes",
    "array": "array",
    "struct": "struct",
    "map": "map",
}
