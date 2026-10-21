# Generated manually for Phase 25.5 - GDPR models

import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenants", "0008_add_tenant_usage_summary"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataExportJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        help_text="Export job status",
                        max_length=20,
                    ),
                ),
                (
                    "storage_path",
                    models.CharField(
                        blank=True,
                        help_text="Path in storage (S3/MinIO) for export archive",
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "download_url",
                    models.URLField(
                        blank=True,
                        help_text="Signed URL for downloading export (short-lived)",
                        max_length=2048,
                        null=True,
                    ),
                ),
                (
                    "download_url_expires_at",
                    models.DateTimeField(
                        blank=True, help_text="When download URL expires", null=True
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, help_text="Error message if status is FAILED", null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True, help_text="When export was completed", null=True
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this export belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_export_jobs",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User requesting data export",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "data_export_jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ErasureRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        help_text="Erasure request status",
                        max_length=20,
                    ),
                ),
                (
                    "requested_at",
                    models.DateTimeField(auto_now_add=True, help_text="When erasure was requested"),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True, help_text="When erasure was completed", null=True
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, help_text="Error message if status is FAILED", null=True
                    ),
                ),
                (
                    "anonymized_fields",
                    models.JSONField(
                        default=list, help_text="List of fields that were anonymized (not deleted)"
                    ),
                ),
                (
                    "deleted_resources",
                    models.JSONField(
                        default=list, help_text="List of resource types that were deleted"
                    ),
                ),
                (
                    "retention_exceptions",
                    models.JSONField(
                        default=list,
                        help_text="List of resources retained due to legal/compliance requirements",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this erasure belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="erasure_requests",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User requesting erasure",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="erasure_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "erasure_requests",
                "ordering": ["-requested_at"],
            },
        ),
        migrations.AddIndex(
            model_name="dataexportjob",
            index=models.Index(fields=["user", "status"], name="data_export_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="dataexportjob",
            index=models.Index(fields=["tenant", "status"], name="data_export_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="dataexportjob",
            index=models.Index(
                fields=["status", "created_at"], name="data_export_status_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="erasurerequest",
            index=models.Index(fields=["user", "status"], name="erasure_req_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="erasurerequest",
            index=models.Index(fields=["tenant", "status"], name="erasure_req_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="erasurerequest",
            index=models.Index(
                fields=["status", "requested_at"], name="erasure_req_status_requested_idx"
            ),
        ),
    ]
