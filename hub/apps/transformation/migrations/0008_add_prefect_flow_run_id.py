"""
285.9.1.4.9 — Add prefect_flow_run_id to PipelineExecution.

CharField(null=True, blank=True, max_length=255) with DB index.
Set after the Prefect run_dbt_transformation flow run is created.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transformation", "0007_add_dbt_execution_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipelineexecution",
            name="prefect_flow_run_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Prefect flow run ID for this execution. Set after Prefect flow run creation.",
                max_length=255,
                null=True,
            ),
        ),
    ]
