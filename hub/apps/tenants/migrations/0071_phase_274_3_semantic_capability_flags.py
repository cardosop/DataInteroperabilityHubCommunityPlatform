"""Phase 274.3 — add ``semantic_capabilities_enabled`` and
``semantic_export_enabled`` per-tenant feature flags.

Default False for both — opt-in capabilities gated by the
HasSemanticCapability DRF permission class.
"""
# Generated migration stub — Django will fill AddField ops when
# ``makemigrations`` runs. The model fields are declared in
# tenants/models.py.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0070_tenant_continuous_compliance_enforcement"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_capabilities_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 274.3 (BR3) — when True, URI dereference and "
                    "semantic relationship endpoints are accessible."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="semantic_export_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 274.3 (BR3) — when True, RDF ingest/export "
                    "endpoints are accessible."
                ),
            ),
        ),
    ]
