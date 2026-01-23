# Generated migration to remove transformation workflow references
# This migration cleans up any workflow instances related to transformation pipelines

from django.db import migrations


def _cleanup_transformation_workflows(apps, schema_editor):
    """Safely cancel transformation workflow instances if table exists"""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if orchestration_workflowinstance table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'orchestration_workflowinstance'
            );
        """
        )
        table_exists = cursor.fetchone()[0]

        if table_exists:
            # Cancel any transformation pipeline workflow instances
            cursor.execute(
                """
                UPDATE orchestration_workflowinstance
                SET status = 'FAILED',
                    error_message = 'Transformation feature removed',
                    updated_at = NOW()
                WHERE workflow_name = 'transformation_pipeline'
                AND status IN ('PENDING', 'RUNNING');
            """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0001_initial"),
    ]

    operations = [
        # Cancel any transformation pipeline workflow instances (if table exists)
        migrations.RunPython(
            code=_cleanup_transformation_workflows,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
