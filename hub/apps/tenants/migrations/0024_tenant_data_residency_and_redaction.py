# Phase 228 X (228.X.4.1 + 228.X.5.1) — additive-only:
#   * data_residency_region (REQ-LIN-X-004)
#   * lineage_redact_field_patterns (REQ-LIN-X-005)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0023_add_archival_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="data_residency_region",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Phase 228 X (REQ-LIN-X-004) — ISO region the tenant's "
                    "data MUST stay in (e.g. eu-west-1). Cross-region lineage "
                    "access requires explicit consent header per F1 contract. "
                    "NULL = legacy tenant with no residency rule."
                ),
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="lineage_redact_field_patterns",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Phase 228 X (REQ-LIN-X-005) — JSON list of regex patterns. "
                    "When the field name on a LineageEdge matches any pattern "
                    "AND the request's tenant_id != edge.tenant_id, the field "
                    "name is replaced with '[REDACTED]' in the API response. "
                    "Empty list = no redaction (legacy)."
                ),
            ),
        ),
    ]
