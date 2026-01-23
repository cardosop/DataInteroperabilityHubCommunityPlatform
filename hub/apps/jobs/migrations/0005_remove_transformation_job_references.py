# Generated migration to remove transformation job references
# This migration cleans up queued transformation jobs and removes TRANSFORMATION_PIPELINE_EXECUTION from choices

from django.db import migrations, models


def _cleanup_transformation_jobs(apps, schema_editor):
    """Safely cancel/fail transformation jobs if jobs_job table exists"""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if jobs_job table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'jobs_job'
            );
        """
        )
        table_exists = cursor.fetchone()[0]

        if table_exists:
            # Cancel all pending/running transformation jobs
            cursor.execute(
                """
                UPDATE jobs_job
                SET status = 'CANCELLED',
                    error_message = 'Transformation feature removed',
                    updated_at = NOW()
                WHERE job_type = 'TRANSFORMATION_PIPELINE_EXECUTION'
                AND status IN ('PENDING', 'RUNNING');
            """
            )
            # Mark all running transformation jobs as FAILED
            cursor.execute(
                """
                UPDATE jobs_job
                SET status = 'FAILED',
                    error_message = 'Transformation feature removed during execution',
                    updated_at = NOW()
                WHERE job_type = 'TRANSFORMATION_PIPELINE_EXECUTION'
                AND status = 'RUNNING';
            """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0004_add_workflow_instance_to_query_execution"),
    ]

    operations = [
        # Cancel all pending/running transformation jobs (if table exists)
        migrations.RunPython(
            code=_cleanup_transformation_jobs,
            reverse_code=migrations.RunPython.noop,
        ),
        # Remove TRANSFORMATION_PIPELINE_EXECUTION from JobType choices
        migrations.AlterField(
            model_name="job",
            name="type",
            field=models.CharField(
                choices=[
                    ("DQ_RUN", "Data Quality Run"),
                    ("COMPLIANCE_RUN", "Compliance Run"),
                    ("CONTRACT_VALIDATION", "Contract Validation"),
                    ("SEMANTIC_MAPPING", "Semantic Mapping"),
                    ("CONTRACT_MIGRATION", "Contract Migration"),
                    ("SCHEDULED_INGESTION", "Scheduled Ingestion"),
                    ("RETENTION_POLICY_ENFORCEMENT", "Retention Policy Enforcement"),
                    ("SEARCH_INDEX_UPDATE", "Search Index Update"),
                    ("ODPS_NORMALIZATION", "ODPS Normalization"),
                    ("ODPS_REF_RESOLUTION", "ODPS $ref Resolution"),
                    ("ODPS_EXPORT", "ODPS Export"),
                    ("ODPS_SEMANTIC_MAPPING", "ODPS Semantic Mapping"),
                    ("ODPS_LINKING", "ODPS Linking"),
                    ("VIRTUAL_QUERY_EXECUTION", "Virtual Query Execution"),
                    ("MARKETPLACE_SYNC", "Marketplace Sync"),
                ],
                help_text="Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc.",
                max_length=50,
            ),
        ),
    ]
