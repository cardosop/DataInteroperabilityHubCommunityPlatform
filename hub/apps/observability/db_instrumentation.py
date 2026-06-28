"""
Database Query Instrumentation

Instrumentation for tracking slow database queries with OpenTelemetry spans.
Creates spans for queries exceeding a configurable threshold (default: 100ms).
"""

import contextlib
import logging
import os
import sys
import time

from django.conf import settings
from django.db import connection
from django.db.backends.utils import CursorWrapper

logger = logging.getLogger(__name__)

# OpenTelemetry availability
OPENTELEMETRY_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


def is_opentelemetry_enabled() -> bool:
    """Check if OpenTelemetry is enabled."""
    if not OPENTELEMETRY_AVAILABLE:
        return False
    return getattr(settings, "OPENTELEMETRY_ENABLED", False)


def get_slow_query_threshold_ms() -> float:
    """Get slow query threshold in milliseconds."""
    return getattr(settings, "OTEL_DB_SLOW_QUERY_THRESHOLD_MS", 100.0)


def extract_table_from_query(sql: str) -> str | None:
    """
    Extract table name from SQL query.

    Args:
        sql: SQL query string

    Returns:
        Table name or None if not found
    """
    sql_upper = sql.upper().strip()

    # Try to extract table name from common patterns
    # SELECT ... FROM table_name
    if "FROM" in sql_upper:
        parts = sql_upper.split("FROM", 1)
        if len(parts) > 1:
            table_part = parts[1].strip().split()[0]
            # Remove quotes and schema prefix, convert to lowercase
            table = table_part.strip("\"'`").split(".")[-1].lower()
            return table

    # INSERT INTO table_name
    if "INSERT INTO" in sql_upper:
        parts = sql_upper.split("INSERT INTO", 1)
        if len(parts) > 1:
            table_part = parts[1].strip().split()[0]
            table = table_part.strip("\"'`").split(".")[-1].lower()
            return table

    # UPDATE table_name
    if "UPDATE" in sql_upper:
        parts = sql_upper.split("UPDATE", 1)
        if len(parts) > 1:
            table_part = parts[1].strip().split()[0]
            table = table_part.strip("\"'`").split(".")[-1].lower()
            return table

    # DELETE FROM table_name
    if "DELETE FROM" in sql_upper:
        parts = sql_upper.split("DELETE FROM", 1)
        if len(parts) > 1:
            table_part = parts[1].strip().split()[0]
            table = table_part.strip("\"'`").split(".")[-1].lower()
            return table

    return None


def extract_operation_from_query(sql: str) -> str:
    """
    Extract operation type from SQL query.

    Args:
        sql: SQL query string

    Returns:
        Operation type (SELECT, INSERT, UPDATE, DELETE, etc.)
    """
    sql_upper = sql.upper().strip()

    if sql_upper.startswith("SELECT"):
        return "SELECT"
    elif sql_upper.startswith("INSERT"):
        return "INSERT"
    elif sql_upper.startswith("UPDATE"):
        return "UPDATE"
    elif sql_upper.startswith("DELETE"):
        return "DELETE"
    elif sql_upper.startswith("CREATE"):
        return "CREATE"
    elif sql_upper.startswith("ALTER"):
        return "ALTER"
    elif sql_upper.startswith("DROP"):
        return "DROP"
    else:
        return "OTHER"


class InstrumentedCursorWrapper(CursorWrapper):
    """
    Wrapper around database cursor that instruments queries with OpenTelemetry spans.

    Creates spans for slow queries (>threshold).
    """

    def execute(self, sql, params=None):
        """Execute SQL query with instrumentation."""
        if not is_opentelemetry_enabled():
            return super().execute(sql, params)

        start_time = time.time()
        slow_threshold_ms = get_slow_query_threshold_ms()

        try:
            result = super().execute(sql, params)
            duration_ms = (time.time() - start_time) * 1000

            # Only create span for slow queries
            if duration_ms >= slow_threshold_ms:
                _create_db_query_span(sql, duration_ms)

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Create span for slow queries even if they fail
            if duration_ms >= slow_threshold_ms:
                span = _create_db_query_span(sql, duration_ms)
                if span:
                    try:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    except Exception:
                        pass

            raise

    def executemany(self, sql, param_list):
        """Execute SQL query multiple times with instrumentation."""
        if not is_opentelemetry_enabled():
            return super().executemany(sql, param_list)

        start_time = time.time()
        slow_threshold_ms = get_slow_query_threshold_ms()

        try:
            result = super().executemany(sql, param_list)
            duration_ms = (time.time() - start_time) * 1000

            # Only create span for slow queries
            if duration_ms >= slow_threshold_ms:
                _create_db_query_span(sql, duration_ms, is_many=True)

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Create span for slow queries even if they fail
            if duration_ms >= slow_threshold_ms:
                span = _create_db_query_span(sql, duration_ms, is_many=True)
                if span:
                    try:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    except Exception:
                        pass

            raise


def _create_db_query_span(sql: str, duration_ms: float, is_many: bool = False):
    """
    Create OpenTelemetry span for a database query.

    Args:
        sql: SQL query string
        duration_ms: Query duration in milliseconds
        is_many: Whether this is an executemany call

    Returns:
        Span instance or None
    """
    try:
        tracer = trace.get_tracer(__name__)

        # Extract operation and table
        operation = extract_operation_from_query(sql)
        table = extract_table_from_query(sql)

        # Create span name
        if table:
            span_name = f"db.{operation.lower()}.{table}"
        else:
            span_name = f"db.{operation.lower()}"

        if is_many:
            span_name = f"{span_name}.many"

        # Start span
        span = tracer.start_as_current_span(span_name)

        # Add attributes
        attributes = {
            "db.operation": operation,
            "db.query.duration_ms": duration_ms,
            "db.system": "postgresql",  # Default to PostgreSQL
        }

        if table:
            attributes["db.table"] = table

        if is_many:
            attributes["db.executemany"] = True

        # Add SQL query (truncated if too long)
        sql_truncated = sql[:500] if len(sql) > 500 else sql
        attributes["db.statement"] = sql_truncated

        # Set attributes
        for key, value in attributes.items():
            with contextlib.suppress(Exception):
                span.set_attribute(key, value)

        # Set status
        span.set_status(Status(StatusCode.OK))

        # End span
        span.end()

        return span
    except Exception as e:
        logger.debug(f"Failed to create DB query span: {e}")
        return None


def instrument_database_connection():
    """
    Instrument Django database connection to use instrumented cursor.

    This should be called during Django startup to enable database query instrumentation.
    """
    if not is_opentelemetry_enabled():
        return

    # Skip instrumentation in test mode to avoid connection issues
    import sys

    if "test" in sys.argv or "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        logger.debug("Skipping database instrumentation in test mode")
        return

    try:
        # Monkey-patch the cursor method to use our instrumented wrapper
        original_cursor = connection.cursor

        def instrumented_cursor():
            # Ensure connection is open before creating cursor
            # This handles cases where connections are closed between operations
            if hasattr(connection, "ensure_connection"):
                try:
                    # Always try to ensure connection is open
                    # This will reopen if closed, or do nothing if already open
                    connection.ensure_connection()
                except Exception:
                    # If connection can't be opened, let the original cursor handle the error
                    # This allows Django's error handling to work properly
                    pass

            try:
                cursor = original_cursor()
                return InstrumentedCursorWrapper(cursor, connection)
            except (Exception, AttributeError) as e:
                # If cursor creation fails due to closed connection, try to reopen and retry once
                # This handles race conditions where connection closes between ensure_connection and cursor()
                if hasattr(connection, "ensure_connection"):
                    try:
                        # Force reconnection by closing and reopening
                        if hasattr(connection, "close"):
                            with contextlib.suppress(Exception):
                                connection.close()
                        connection.ensure_connection()
                        cursor = original_cursor()
                        return InstrumentedCursorWrapper(cursor, connection)
                    except Exception:
                        # If retry fails, let the original error propagate
                        raise e
                else:
                    raise

        connection.cursor = instrumented_cursor
        logger.info("Database query instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument database connection: {e}")
