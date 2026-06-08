"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_rename_jobs_tenant_status_idx_jobs_tenant__a46df1_idx_and_more"),
        ("jobs", "0003_add_workflow_instance_to_pipeline_execution"),
        ("jobs", "0005_add_job_priority"),
        ("jobs", "0005_remove_transformation_job_references"),
        ("jobs", "0017_jobtype_retention_enforcement_sweep"),
        ("jobs", "0018_enable_rls_failed_job_dlq"),
        ("jobs", "0019_merge_20260513_1157"),
        ("jobs", "0022_alter_job_type"),
        ("jobs", "0023_add_dependency_statuses"),
    ]

    operations = [
    ]
