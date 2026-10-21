# Generated manually — Phase 232.5 DPIA_REVIEW_DUE JobType.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0015_jobtype_ropa_generate"),
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
                    ("TRANSFORMATION", "Transformation Pipeline"),
                    ("SEMANTIC_EXPORT_LARGE", "Semantic Export (large)"),
                    ("SEMANTIC_SNAPSHOT", "Semantic Snapshot"),
                    ("ONTOLOGY_VALIDATE", "Ontology Validate"),
                    ("LDN_OUTBOUND_DELIVERY", "LDN Outbound Delivery"),
                    ("DSAR_STATUTORY_CLOCK_CHECK", "DSAR Statutory Clock Check"),
                    ("BREACH_NOTIFICATION_CLOCK_CHECK", "Breach Notification Clock Check"),
                    ("ROPA_GENERATE", "RoPA Generate"),
                    ("DPIA_REVIEW_DUE", "DPIA Review Due"),
                ],
                help_text="Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc.",
                max_length=50,
            ),
        ),
    ]
