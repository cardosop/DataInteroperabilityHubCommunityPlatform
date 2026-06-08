"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0033_add_ingestion_pipeline_trigger_edge_types"),
        ("contracts", "0038_enable_rls_openlineage_ingest_api_key"),
    ]

    operations = [
    ]
