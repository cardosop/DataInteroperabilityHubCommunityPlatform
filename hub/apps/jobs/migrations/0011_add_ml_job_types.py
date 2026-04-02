"""Add ML_TRAINING and ML_INFERENCE to JobType choices (Phase 114A.11).

Django TextChoices changes only require an AlterField on the `type` column
to widen the CHECK constraint / advertise the new choices.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0010_job_status_check_constraint"),
    ]

    operations = [
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
                    ("ML_TRAINING", "ML Training"),
                    ("ML_INFERENCE", "ML Inference"),
                ],
                help_text="Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc.",
                max_length=50,
            ),
        ),
    ]
