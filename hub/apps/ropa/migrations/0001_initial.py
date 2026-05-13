# Generated for Phase 232.4 — RoPA artefacts.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobs", "0015_jobtype_ropa_generate"),
        ("tenants", "0045_tenant_compliance_ropa_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="RopaGeneration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("regulation", models.CharField(help_text="Uppercase regulation key (GDPR, LGPD, ...)", max_length=32)),
                ("output_format", models.CharField(choices=[("json", "JSON"), ("csv", "CSV"), ("pdf", "PDF"), ("docx", "DOCX")], max_length=16)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=20)),
                ("object_key", models.CharField(blank=True, default="", max_length=1024)),
                ("content_sha256", models.CharField(blank=True, default="", max_length=64)),
                ("byte_size", models.PositiveBigIntegerField(default=0)),
                ("cache_generation", models.PositiveIntegerField(default=0, help_text="Invalidation generation counter snapshot at build time.")),
                ("gaps_json", models.JSONField(blank=True, default=list)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ropa_generations_created", to=settings.AUTH_USER_MODEL)),
                ("job", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ropa_generations", to="jobs.job")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ropa_generations", to="tenants.tenant")),
            ],
            options={
                "db_table": "ropa_generations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ropageneration",
            index=models.Index(fields=["tenant", "status"], name="ropa_gener_tenant__6e4e6d_idx"),
        ),
        migrations.AddIndex(
            model_name="ropageneration",
            index=models.Index(fields=["tenant", "created_at"], name="ropa_gener_tenant__dfc7e4_idx"),
        ),
    ]
