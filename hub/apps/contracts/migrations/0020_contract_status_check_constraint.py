"""Phase 92.7 — CheckConstraint for Contract.status field."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0019_add_performance_indexes"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="contract",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["DRAFT", "ACTIVE", "RETIRED"]
                ),
                name="contract_status_valid",
            ),
        ),
    ]
