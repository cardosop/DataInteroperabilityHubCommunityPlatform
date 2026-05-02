# Phase 230.12 (REQ-SEM-LDN-001) — additive: per-tenant capability
# gate for W3C Linked Data Notifications.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0027_tenant_semantic_custom_ontology_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_ldn_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.12 (REQ-SEM-LDN-001) — when True, the "
                    "tenant's LDN inbox accepts signed RDF "
                    "notifications from allow-listed partners and "
                    "the platform fires outbound notifications on "
                    "resource updates. Default False."
                ),
            ),
        ),
    ]
