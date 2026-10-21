"""
W1.11 (R2-S3/S4) — SQL-injection safety helpers for the warehouse SQL
compilers (``dq`` and ``compliance``).

Client-influenced inputs reach the compilers three ways:

  - **Identifiers** (column names, table FQNs) are interpolated raw into
    the generated SQL.  They are validated against the strict unquoted-
    identifier grammar shared by Snowflake/BigQuery/Databricks and
    REJECTED otherwise — the design's "refuse raw identifiers" branch.
    (Per-site dialect quoting was rejected as the primary fix: it would
    change every compiled SQL shape and churn the existing pins.)
  - **Literals** (accepted values, regex patterns) are string-escaped
    (single quotes doubled) before interpolation.
  - **Numeric parameters** (min/max, hours/days) must be real numbers —
    never strings that could splice SQL.

``SQLSafetyError`` subclasses ``ValueError`` so the existing service-layer
``except Exception`` run-failure paths keep working unchanged.
"""

from __future__ import annotations

import re
from numbers import Real

# Unquoted identifier grammar shared by Snowflake/BigQuery/Databricks:
# start with a letter or underscore, continue with letters/digits/_/$.
# No quote, whitespace, comment marker, or operator char can pass.
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*\Z")


class SQLSafetyError(ValueError):
    """Raised when a client-influenced input cannot compile to safe SQL."""


def validate_sql_identifier(value: object, what: str) -> str:
    """Validate a single SQL identifier (column name); raise or return it."""
    if not isinstance(value, str) or not _SQL_IDENTIFIER_RE.match(value):
        raise SQLSafetyError(f"invalid {what} identifier")
    return value


def validate_table_fqn(value: object) -> str:
    """Validate a dotted fully-qualified table name (1+ simple segments)."""
    if not isinstance(value, str) or not value.strip():
        raise SQLSafetyError("invalid table_fqn")
    segments = value.split(".")
    if not all(_SQL_IDENTIFIER_RE.match(segment) for segment in segments):
        raise SQLSafetyError("invalid table_fqn identifier")
    return value


def escape_sql_literal(value: object) -> str:
    """Escape a value interpolated inside a single-quoted SQL literal."""
    return str(value).replace("'", "''")


def escape_regex_literal(value: object, warehouse_type: str) -> str:
    """Escape a regex pattern for the dialect's regex-literal context.

    BigQuery regexes compile into ``r'...'`` raw strings, where the
    quote escape is backslash (raw strings still decode ``\\\\`` and
    ``\\'``); Snowflake/Databricks use plain ``'...'`` literals with
    ANSI quote doubling.  Backslashes pass through unchanged there —
    all three dialects treat them literally in plain string literals.
    """
    text = str(value)
    if warehouse_type == "BIGQUERY":
        return text.replace("\\", "\\\\").replace("'", "\\'")
    return text.replace("'", "''")


def sql_number(value: object, what: str) -> Real:
    """Require a real number (bool excluded — it subclasses int)."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SQLSafetyError(f"{what} must be a number")
    return value
