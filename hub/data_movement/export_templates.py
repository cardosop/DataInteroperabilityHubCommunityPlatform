"""
285.6.4.3 — Export templates for common dlt pipeline configurations.

Pre-defined templates for S3, Snowflake, BigQuery, and custom exports.
"""
from __future__ import annotations
from typing import Any, Dict

EXPORT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "S3_DAILY_DUMP": {
        "name": "S3 Daily Dump",
        "destination_type": "S3",
        "schedule": "DAILY",
        "description": "Daily full export to S3 in Parquet format with partitioning by date.",
        "config": {
            "format": "parquet",
            "partitioning": "date",
            "compression": "snappy",
        },
    },
    "S3_INCREMENTAL_SYNC": {
        "name": "S3 Incremental Sync",
        "destination_type": "S3",
        "schedule": "CUSTOM_CRON",
        "cron": "0 */6 * * *",
        "description": "Incremental sync to S3 every 6 hours. Only changed files are exported.",
        "config": {
            "format": "parquet",
            "write_disposition": "merge",
            "compression": "snappy",
        },
    },
    "SNOWFLAKE_WEEKLY_SYNC": {
        "name": "Snowflake Weekly Sync",
        "destination_type": "SNOWFLAKE_TABLE",
        "schedule": "WEEKLY",
        "description": "Weekly sync to Snowflake with schema evolution and merge dedup.",
        "config": {
            "write_disposition": "merge",
            "schema_evolution": True,
        },
    },
    "BIGQUERY_HOURLY": {
        "name": "BigQuery Hourly",
        "destination_type": "BIGQUERY_TABLE",
        "schedule": "CUSTOM_CRON",
        "cron": "0 * * * *",
        "description": "Hourly sync to BigQuery with partition by ingestion time.",
        "config": {
            "write_disposition": "merge",
            "partition_by": "_ingested_at",
        },
    },
    "DATABRICKS_DAILY_SYNC": {
        "name": "Databricks Daily Sync",
        "destination_type": "DATABRICKS_TABLE",
        "schedule": "DAILY",
        "description": "Daily sync to Databricks Unity Catalog with schema evolution.",
        "config": {
            "write_disposition": "merge",
            "schema_evolution": True,
        },
    },
    "ATHENA_DAILY_SYNC": {
        "name": "Athena Daily Sync",
        "destination_type": "ATHENA_TABLE",
        "schedule": "DAILY",
        "description": "Daily sync to Athena with Parquet format and Glue catalog integration.",
        "config": {
            "format": "parquet",
            "write_disposition": "replace",
        },
    },
    "HTTP_POST_EXPORT": {
        "name": "HTTP POST Export",
        "destination_type": "HTTP",
        "schedule": "CUSTOM_CRON",
        "description": "Export to HTTP endpoint via POST with JSON payload.",
        "config": {
            "format": "json",
            "method": "POST",
        },
    },
}


def get_template(template_name: str) -> Dict[str, Any] | None:
    """Return an export template by name, or None if not found."""
    return EXPORT_TEMPLATES.get(template_name)


def list_templates() -> list[Dict[str, Any]]:
    """List all available export templates with names and descriptions."""
    return [
        {"name": name, "description": t["description"], "destination_type": t["destination_type"]}
        for name, t in EXPORT_TEMPLATES.items()
    ]
