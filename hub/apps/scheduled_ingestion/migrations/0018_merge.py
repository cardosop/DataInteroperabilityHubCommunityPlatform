"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0001_initial"),
        ("scheduled_ingestion", "0002_add_ingestion_templates"),
        ("scheduled_ingestion", "0003_add_dlq_and_cost_tracking"),
        ("scheduled_ingestion", "0014_alter_scheduledingestion_credential_ref_and_more"),
        ("scheduled_ingestion", "0015_add_dependency_statuses"),
        ("scheduled_ingestion", "0017_enable_rls_scheduled_ingestion_runs"),
    ]

    operations = [
    ]
