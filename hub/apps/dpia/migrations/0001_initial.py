# Generated manually — Phase 232.5 DPIA initial.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("assets", "0019_asset_ropa_metadata_and_purposes"),
        ("tenants", "0046_tenant_compliance_dpia_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dpia",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=512)),
                ("regime", models.CharField(default="GDPR", help_text="Primary regulation key (GDPR, LGPD, ...).", max_length=32)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("IN_REVIEW", "In review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("REQUIRES_CONSULTATION", "Requires consultation"), ("SUPERSEDED", "Superseded")], db_index=True, default="DRAFT", max_length=32)),
                ("version", models.PositiveIntegerField(default=1, help_text="Monotonic per (tenant, asset) lineage.")),
                ("wizard_payload", models.JSONField(blank=True, default=dict, help_text="Structured wizard answers (steps, narrative fields).")),
                ("risk_residual", models.CharField(blank=True, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")], default="", help_text="Recorded residual risk after mitigations (set at review).", max_length=16)),
                ("next_review_due_at", models.DateTimeField(blank=True, db_index=True, help_text="When an approved DPIA must re-enter review (typically +12 months).", null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("dpo_summary", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("asset", models.ForeignKey(blank=True, help_text="When set, DPIA is scoped to this catalog asset.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="dpias", to="assets.asset")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dpias_created", to=settings.AUTH_USER_MODEL)),
                ("previous_version", models.ForeignKey(blank=True, help_text="Prior version for diff / lineage.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="next_versions", to="dpia.Dpia")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dpias_reviewed", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dpias", to="tenants.tenant")),
            ],
            options={
                "db_table": "dpia",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="dpia",
            index=models.Index(fields=["tenant", "status"], name="dpia_tenant_i_9f80b2_idx"),
        ),
        migrations.AddIndex(
            model_name="dpia",
            index=models.Index(fields=["tenant", "asset", "status"], name="dpia_tenant_i_a1b2c3_idx"),
        ),
        migrations.AddIndex(
            model_name="dpia",
            index=models.Index(fields=["tenant", "next_review_due_at"], name="dpia_tenant_i_d4e5f6_idx"),
        ),
    ]
