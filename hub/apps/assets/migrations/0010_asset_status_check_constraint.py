"""Phase 92.7 — CheckConstraint for Asset.status field."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0009_asset_search_vector"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "DRAFT", "ACTIVE", "PUBLIC", "RETIRED",
                    ]
                ),
                name="asset_status_valid",
            ),
        ),
    ]
