# 277.B.086 — consent purpose versioning + grant-version tracking
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0002_enable_rls_consent"),
    ]

    operations = [
        migrations.AddField(
            model_name="consentpurpose",
            name="version",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Monotonic version — bumped on substance changes so stale grants trigger re-consent.",
            ),
        ),
        migrations.AddField(
            model_name="consentrecord",
            name="purpose_version_at_grant",
            field=models.PositiveIntegerField(
                default=1,
                help_text="ConsentPurpose.version that was current when this grant was recorded.",
            ),
        ),
    ]
