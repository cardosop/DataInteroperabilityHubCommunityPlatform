"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0001_initial_observability"),
        ("observability", "0002_add_pipeline_sla_incident_models"),
        ("observability", "0003_add_observability_query_indexes"),
        ("observability", "0003_remove_transformation_pipeline_type"),
        ("observability", "0004_merge_20260116_1227"),
        ("observability", "0007_enable_rls_observability"),
    ]

    operations = [
    ]
