# Generated migration for scheduled export models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledExport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Scheduled export name (unique per tenant)", max_length=255
                    ),
                ),
                (
                    "schedule_config",
                    models.JSONField(
                        help_text="Schedule configuration (cron expression, timezone)"
                    ),
                ),
                (
                    "destination_type",
                    models.CharField(
                        choices=[
                            ("S3", "Amazon S3"),
                            ("GCS", "Google Cloud Storage"),
                            ("AZURE_BLOB", "Azure Blob Storage"),
                        ],
                        help_text="Destination type: S3, GCS, AZURE_BLOB",
                        max_length=50,
                    ),
                ),
                (
                    "destination_config",
                    models.JSONField(
                        help_text="Destination configuration (connection details, credentials, paths) stored securely. Credentials are masked in API and logs."
                    ),
                ),
                (
                    "source_scope",
                    models.JSONField(
                        help_text="Source scope: asset_ids, dataset_ids, file_ids, or contract_id"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("PAUSED", "Paused"), ("ERROR", "Error")],
                        default="ACTIVE",
                        help_text="Status: ACTIVE, PAUSED, ERROR",
                        max_length=20,
                    ),
                ),
                (
                    "next_run_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Next scheduled run time (calculated based on schedule)",
                        null=True,
                    ),
                ),
                (
                    "last_run_at",
                    models.DateTimeField(blank=True, help_text="Last run time", null=True),
                ),
                (
                    "last_run_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        help_text="Status of last run: RUNNING, COMPLETED, FAILED, CANCELLED",
                        max_length=20,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this scheduled export belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scheduled_exports",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "scheduled_exports",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ScheduledExportRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="RUNNING",
                        help_text="Run status: RUNNING, COMPLETED, FAILED, CANCELLED",
                        max_length=20,
                    ),
                ),
                (
                    "items_found",
                    models.IntegerField(default=0, help_text="Number of items found for export"),
                ),
                (
                    "items_exported",
                    models.IntegerField(
                        default=0, help_text="Number of items successfully exported"
                    ),
                ),
                (
                    "items_failed",
                    models.IntegerField(
                        default=0, help_text="Number of items that failed to export"
                    ),
                ),
                (
                    "result_json",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Run result data (items exported, errors, etc.)",
                        null=True,
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(blank=True, help_text="When run started", null=True),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True, help_text="When run completed (success or failure)", null=True
                    ),
                ),
                (
                    "prefect_flow_run_id",
                    models.CharField(
                        blank=True, help_text="Prefect flow run ID", max_length=255, null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scheduled_export",
                    models.ForeignKey(
                        help_text="Scheduled export this run belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="scheduled_export.scheduledexport",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this export run belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scheduled_export_runs",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "scheduled_export_runs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ExportRunCost",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                (
                    "cost_components",
                    models.JSONField(
                        default=dict,
                        help_text="Cost components breakdown (storage, compute, network, etc.)",
                    ),
                ),
                (
                    "calculated_at",
                    models.DateTimeField(auto_now_add=True, help_text="When cost was calculated"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "run",
                    models.ForeignKey(
                        help_text="Export run this cost belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="costs",
                        to="scheduled_export.scheduledexportrun",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this cost belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="export_run_costs",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "export_run_costs",
                "ordering": ["-calculated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="scheduledexport",
            constraint=models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_scheduled_export_name_per_tenant"
            ),
        ),
        # Indexes are defined in model Meta class and will be created automatically
    ]
