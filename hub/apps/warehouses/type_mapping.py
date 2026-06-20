"""
Phase 275.A.15 — per-warehouse type → Hub canonical type mapping.

Without this registry, queries return numerically-incorrect data
due to precision loss or varying type representations across warehouses.
"""

from __future__ import annotations

from enum import Enum


class LossyConversionPolicy(str, Enum):
    """Per-asset policy for handling lossy type conversions."""

    STRICT_ERROR = "STRICT_ERROR"
    LOSSY_WARN = "LOSSY_WARN"
    LOSSY_SILENT = "LOSSY_SILENT"


# Hub canonical types.
CANONICAL_STRING = "string"
CANONICAL_INTEGER = "integer"
CANONICAL_FLOAT = "float"
CANONICAL_BOOLEAN = "boolean"
CANONICAL_DECIMAL = "decimal"
CANONICAL_TIMESTAMP = "timestamp"
CANONICAL_DATE = "date"
CANONICAL_JSON = "json"
CANONICAL_BINARY = "binary"
CANONICAL_ARRAY = "array"


# Phase 275.A.15 — per-warehouse type mappings.
# Decimals MUST be serialised as strings on the JSON path (RFC 7159)
# and native on the Arrow path (no precision loss).

SNOWFLAKE_TYPE_MAP: dict[str, str] = {
    "VARCHAR": CANONICAL_STRING,
    "TEXT": CANONICAL_STRING,
    "CHAR": CANONICAL_STRING,
    "INTEGER": CANONICAL_INTEGER,
    "INT": CANONICAL_INTEGER,
    "BIGINT": CANONICAL_INTEGER,
    "NUMBER": CANONICAL_DECIMAL,
    "NUMERIC": CANONICAL_DECIMAL,
    "FLOAT": CANONICAL_FLOAT,
    "DOUBLE": CANONICAL_FLOAT,
    "BOOLEAN": CANONICAL_BOOLEAN,
    "TIMESTAMP_NTZ": CANONICAL_TIMESTAMP,
    "TIMESTAMP_TZ": CANONICAL_TIMESTAMP,
    "TIMESTAMP_LTZ": CANONICAL_TIMESTAMP,
    "DATE": CANONICAL_DATE,
    "VARIANT": CANONICAL_JSON,
    "OBJECT": CANONICAL_JSON,
    "ARRAY": CANONICAL_ARRAY,
    "GEOGRAPHY": CANONICAL_JSON,
    "BINARY": CANONICAL_BINARY,
}

BIGQUERY_TYPE_MAP: dict[str, str] = {
    "STRING": CANONICAL_STRING,
    "INT64": CANONICAL_INTEGER,
    "INTEGER": CANONICAL_INTEGER,
    "FLOAT64": CANONICAL_FLOAT,
    "FLOAT": CANONICAL_FLOAT,
    "BOOL": CANONICAL_BOOLEAN,
    "BOOLEAN": CANONICAL_BOOLEAN,
    "TIMESTAMP": CANONICAL_TIMESTAMP,
    "DATETIME": CANONICAL_TIMESTAMP,
    "DATE": CANONICAL_DATE,
    "NUMERIC": CANONICAL_DECIMAL,
    "BIGNUMERIC": CANONICAL_DECIMAL,
    "JSON": CANONICAL_JSON,
    "GEOGRAPHY": CANONICAL_JSON,
    "STRUCT": CANONICAL_JSON,
    "BYTES": CANONICAL_BINARY,
    "ARRAY": CANONICAL_ARRAY,
}

DATABRICKS_TYPE_MAP: dict[str, str] = {
    "STRING": CANONICAL_STRING,
    "INT": CANONICAL_INTEGER,
    "INTEGER": CANONICAL_INTEGER,
    "BIGINT": CANONICAL_INTEGER,
    "FLOAT": CANONICAL_FLOAT,
    "DOUBLE": CANONICAL_FLOAT,
    "DECIMAL": CANONICAL_DECIMAL,
    "BOOLEAN": CANONICAL_BOOLEAN,
    "TIMESTAMP": CANONICAL_TIMESTAMP,
    "DATE": CANONICAL_DATE,
    "MAP": CANONICAL_JSON,
    "STRUCT": CANONICAL_JSON,
    "ARRAY": CANONICAL_ARRAY,
    "BINARY": CANONICAL_BINARY,
}

ATHENA_TYPE_MAP: dict[str, str] = {
    "varchar": CANONICAL_STRING,
    "string": CANONICAL_STRING,
    "int": CANONICAL_INTEGER,
    "integer": CANONICAL_INTEGER,
    "bigint": CANONICAL_INTEGER,
    "float": CANONICAL_FLOAT,
    "double": CANONICAL_FLOAT,
    "decimal": CANONICAL_DECIMAL,
    "boolean": CANONICAL_BOOLEAN,
    "timestamp": CANONICAL_TIMESTAMP,
    "date": CANONICAL_DATE,
    "array": CANONICAL_ARRAY,
    "struct": CANONICAL_JSON,
    "binary": CANONICAL_BINARY,
    "json": CANONICAL_JSON,
}

WAREHOUSE_TYPE_MAPS: dict[str, dict[str, str]] = {
    "SNOWFLAKE": SNOWFLAKE_TYPE_MAP,
    "BIGQUERY": BIGQUERY_TYPE_MAP,
    "DATABRICKS": DATABRICKS_TYPE_MAP,
    "ATHENA": ATHENA_TYPE_MAP,
}


def map_warehouse_type(warehouse: str, source_type: str) -> str:
    """Map a warehouse-specific type to the Hub canonical type.

    Returns CANONICAL_STRING for unknown types (safe fallback).
    """
    type_map = WAREHOUSE_TYPE_MAPS.get(warehouse.upper(), {})
    return type_map.get(source_type.upper(), CANONICAL_STRING)
