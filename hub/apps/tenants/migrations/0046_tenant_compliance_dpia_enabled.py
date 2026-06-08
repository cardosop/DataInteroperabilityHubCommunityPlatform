# Generated manually — Phase 232.5 DPIA tenant flag.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0045_tenant_compliance_ropa_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_dpia_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When True, DPIA APIs, wizard, and DPO review queue are enabled for this tenant.",
            ),
        ),
    ]
