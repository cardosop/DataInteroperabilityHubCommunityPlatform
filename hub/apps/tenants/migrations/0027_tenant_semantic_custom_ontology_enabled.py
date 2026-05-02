# Phase 230.10 (REQ-SEM-ONTO-002) — additive: per-tenant capability
# gate for custom-ontology registration. Default False — feature is
# rolled out per tenant; the viewset returns 403 when this is False
# regardless of user role.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0026_tenant_semantic_inference_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_custom_ontology_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.10 (REQ-SEM-ONTO-002) — when True, "
                    "TENANT_ADMINs may upload and manage custom "
                    "ontologies via /api/v1/semantic/ontologies/. "
                    "When False the endpoint returns 403 regardless "
                    "of role."
                ),
            ),
        ),
    ]
