import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenants", "0041_tenantconfig_compliance_risk_threshold"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentPurpose",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(help_text="Stable machine key, unique per tenant (e.g. signup.privacy).", max_length=128)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("retention_days", models.PositiveIntegerField(blank=True, help_text="Optional retention hint for this purpose (informational).", null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("iab_purpose_id", models.CharField(blank=True, default="", max_length=32)),
                ("iab_special_feature_optins", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_purposes",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "consent_purpose",
            },
        ),
        migrations.CreateModel(
            name="ConsentRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("GRANTED", "Granted"), ("REVOKED", "Revoked")], default="GRANTED", max_length=16)),
                ("granted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("canonical_payload", models.JSONField(blank=True, default=dict)),
                ("proof_hmac", models.CharField(blank=True, default="", max_length=64)),
                ("signing_key_index", models.PositiveSmallIntegerField(default=0, help_text="Index into the tenant key ring (0 = newest) used when the proof was stamped.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "purpose",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consent_records",
                        to="consent.consentpurpose",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_records",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "consent_record",
            },
        ),
        migrations.AddConstraint(
            model_name="consentpurpose",
            constraint=models.UniqueConstraint(fields=("tenant", "key"), name="consent_purpose_tenant_key_uniq"),
        ),
        migrations.AddIndex(
            model_name="consentpurpose",
            index=models.Index(fields=["tenant", "is_active"], name="consent_purpos_tenant__bd29e8_idx"),
        ),
        migrations.AddConstraint(
            model_name="consentrecord",
            constraint=models.UniqueConstraint(
                fields=("tenant", "user", "purpose"),
                name="consent_record_tenant_user_purpose_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="consentrecord",
            index=models.Index(fields=["tenant", "status"], name="consent_record_tenant__45170b_idx"),
        ),
        migrations.AddIndex(
            model_name="consentrecord",
            index=models.Index(fields=["tenant", "user"], name="consent_record_tenant__76bb80_idx"),
        ),
    ]
