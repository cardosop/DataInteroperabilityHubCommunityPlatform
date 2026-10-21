# Generated migration to remove TRANSFORMATION from PipelineExecution pipeline_type choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0002_add_pipeline_sla_incident_models'),
    ]

    operations = [
        # Remove TRANSFORMATION from pipeline_type choices
        migrations.AlterField(
            model_name='pipelineexecution',
            name='pipeline_type',
            field=models.CharField(
                choices=[
                    ('SCHEDULED_INGESTION', 'Scheduled Ingestion'),
                    ('DQ_RUN', 'Data Quality Run'),
                    ('COMPLIANCE_RUN', 'Compliance Run'),
                    ('CONTRACT_VALIDATION', 'Contract Validation'),
                    ('SEMANTIC_MAPPING', 'Semantic Mapping'),
                ],
                db_index=True,
                help_text='Type of pipeline',
                max_length=50
            ),
        ),
        # Delete any existing transformation pipeline execution records
        migrations.RunSQL(
            sql="DELETE FROM pipeline_executions WHERE pipeline_type = 'TRANSFORMATION';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
