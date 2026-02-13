# Generated manually for Phase 25.1.3 - TenantUsageSummary

import hub.apps.tenants.models
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0007_add_tenant_plan_and_plan_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantUsageSummary",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "period_start",
                    models.DateTimeField(
                        help_text="Start of the usage period (typically start of month)"
                    ),
                ),
                (
                    "period_end",
                    models.DateTimeField(
                        help_text="End of the usage period (typically end of month)"
                    ),
                ),
                (
                    "api_calls_count",
                    models.BigIntegerField(default=0, help_text="Total API calls in period"),
                ),
                (
                    "asset_count",
                    models.IntegerField(default=0, help_text="Total assets (current count)"),
                ),
                (
                    "dataset_count",
                    models.IntegerField(default=0, help_text="Total datasets (current count)"),
                ),
                (
                    "scheduled_ingestion_runs_count",
                    models.IntegerField(
                        default=0, help_text="Total scheduled ingestion runs in period"
                    ),
                ),
                (
                    "scheduled_export_runs_count",
                    models.IntegerField(
                        default=0, help_text="Total scheduled export runs in period"
                    ),
                ),
                (
                    "storage_bytes",
                    models.BigIntegerField(default=0, help_text="Total storage used in bytes"),
                ),
                (
                    "ingestion_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Total cost for scheduled ingestion runs in period",
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "calculated_at",
                    models.DateTimeField(
                        auto_now=True, help_text="When this summary was last calculated"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this usage summary belongs to",
                        on_delete=models.CASCADE,
                        related_name="usage_summaries",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "tenant_usage_summaries",
                "ordering": ["-period_start"],
            },
        ),
        migrations.AddIndex(
            model_name="tenantusagesummary",
            index=models.Index(
                fields=["tenant", "period_start"], name="tenant_usage_tenant_period_start_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="tenantusagesummary",
            index=models.Index(
                fields=["tenant", "period_end"], name="tenant_usage_tenant_period_end_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="tenantusagesummary",
            index=models.Index(
                fields=["period_start", "period_end"], name="tenant_usage_period_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="tenantusagesummary",
            constraint=models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="unique_tenant_period_usage_summary",
            ),
        ),
    ]
