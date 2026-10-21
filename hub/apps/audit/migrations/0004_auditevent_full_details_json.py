from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_add_archival_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="full_details_json",
            field=models.JSONField(
                blank=True,
                help_text=(
                    "Restricted original details. Access ONLY via "
                    "get_full_details(actor) with TENANT_ADMIN guard."
                ),
                null=True,
            ),
        ),
    ]
