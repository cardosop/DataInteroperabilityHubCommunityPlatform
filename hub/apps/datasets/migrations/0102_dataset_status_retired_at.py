# Phase 260.1.C.1 / C.2 — dataset retirement when backing file is hard-deleted.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0101_enable_rls_datasets"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
            name="status",
            field=models.CharField(
                choices=[("ACTIVE", "Active"), ("RETIRED", "Retired")],
                db_index=True,
                default="ACTIVE",
                help_text="ACTIVE = normal; RETIRED = backing file hard-deleted per Phase 260.1.C.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="dataset",
            name="retired_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When the dataset was retired because its source file was hard-deleted.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="dataset",
            index=models.Index(
                fields=["tenant", "status"],
                name="datasets_tenant_status_idx",
            ),
        ),
    ]
