# Phase 260.1.A.2 — per-tenant grace between API delete and hard purge.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0049_tenantplan_compliance_pro_pack"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="file_soft_delete_grace_days",
            field=models.PositiveIntegerField(
                default=30,
                validators=[
                    django.core.validators.MinValueValidator(7),
                    django.core.validators.MaxValueValidator(365),
                ],
                help_text=(
                    "Phase 260.1.A — days after API file delete (DELETING) before "
                    "purge_deleted_files may remove the object from storage and "
                    "hard-delete the row. Bounds [7, 365]."
                ),
            ),
        ),
    ]
