# Phase 232.6 — asset ↔ processor M2M through table (tenant-scoped for RLS)

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0019_asset_ropa_metadata_and_purposes"),
        ("processor_agreements", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetProcessorMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="_processor_links", to="assets.asset")),
                ("processor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="_asset_links", to="processor_agreements.processor")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="asset_processor_links", to="tenants.tenant")),
            ],
            options={
                "db_table": "pa_asset_processor",
            },
        ),
        migrations.AddConstraint(
            model_name="assetprocessormembership",
            constraint=models.UniqueConstraint(fields=("asset", "processor"), name="pa_ast_proc_uniq"),
        ),
        migrations.AddIndex(
            model_name="assetprocessormembership",
            index=models.Index(fields=["tenant", "processor"], name="pa_ast_proc_tenant__2c8d_idx"),
        ),
    ]
