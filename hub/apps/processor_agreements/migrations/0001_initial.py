# Phase 232.6 — processor registry + agreements

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0047_tenant_compliance_processor_agreements_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Processor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("legal_name", models.CharField(blank=True, default="", max_length=512)),
                ("country_code", models.CharField(blank=True, default="", help_text="ISO 3166-1 alpha-2 (optional).", max_length=2)),
                ("website", models.URLField(blank=True, default="", help_text="Public website; validated for SSRF when non-empty.", max_length=2048)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="processors", to="tenants.tenant")),
            ],
            options={
                "db_table": "pa_processor",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ProcessorAgreement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("agreement_type", models.CharField(choices=[("DPA", "Data Processing Agreement"), ("BAA", "Business Associate Agreement"), ("SCC", "Standard Contractual Clause"), ("BCR", "Binding Corporate Rules")], max_length=16)),
                ("document_uri", models.URLField(max_length=2048)),
                ("document_hash", models.CharField(help_text="SHA-256 hex digest of agreement bytes at registration time.", max_length=64)),
                ("effective_from", models.DateField()),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("sub_processors_declared", models.JSONField(blank=True, default=list, help_text="Structured list of named sub-processors disclosed under the agreement.")),
                ("jurisdiction_region", models.CharField(blank=True, default="", help_text="Region hint for type-specific validation (e.g. US for BAA).", max_length=8)),
                ("registration_reference", models.CharField(blank=True, default="", help_text="Supervisory register id / corporate instrument reference (esp. BCR).", max_length=512)),
                ("transfer_mechanism_summary", models.TextField(blank=True, default="", help_text="Required detail for SCC-style transfers.")),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("EXPIRED", "Expired"), ("SUPERSEDED", "Superseded")], default="ACTIVE", max_length=16)),
                ("expiry_warn_windows_sent", models.JSONField(blank=True, default=list, help_text="Which day-threshold notifications have fired (e.g. [60, 30, 7]).")),
                ("details_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processor_agreements_created", to=settings.AUTH_USER_MODEL)),
                ("processor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agreements", to="processor_agreements.processor")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="processor_agreements", to="tenants.tenant")),
            ],
            options={
                "db_table": "pa_agreement",
                "ordering": ["-effective_from"],
            },
        ),
        migrations.AddIndex(
            model_name="processor",
            index=models.Index(fields=["tenant", "name"], name="pa_processor_tenant__7726c5_idx"),
        ),
        migrations.AddConstraint(
            model_name="processor",
            constraint=models.UniqueConstraint(fields=("tenant", "name"), name="pa_proc_tnt_name_uniq"),
        ),
        migrations.AddIndex(
            model_name="processoragreement",
            index=models.Index(fields=["tenant", "status"], name="pa_agreement_tenant__5df5b4_idx"),
        ),
        migrations.AddIndex(
            model_name="processoragreement",
            index=models.Index(fields=["tenant", "expires_on"], name="pa_agreement_tenant__8f3e12_idx"),
        ),
        migrations.AddIndex(
            model_name="processoragreement",
            index=models.Index(fields=["processor", "agreement_type"], name="pa_agreement_process_8a90bd_idx"),
        ),
    ]
