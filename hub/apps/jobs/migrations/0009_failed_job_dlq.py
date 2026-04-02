"""
Phase 91.7 — FailedJobDLQ model migration.

Dead-letter queue for jobs that failed after exhausting all retries.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0008_phase76_side_effect_outbox"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FailedJobDLQ",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "job_id",
                    models.UUIDField(
                        db_index=True,
                        help_text="Original Job UUID that failed",
                    ),
                ),
                (
                    "queue",
                    models.CharField(
                        max_length=100,
                        help_text="RQ queue name the job was on",
                    ),
                ),
                (
                    "func_name",
                    models.CharField(
                        max_length=255,
                        help_text="Fully-qualified function name",
                    ),
                ),
                (
                    "args_json",
                    models.JSONField(
                        default=dict,
                        help_text="Serialised positional and keyword arguments",
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        help_text="Final error message",
                    ),
                ),
                (
                    "traceback",
                    models.TextField(
                        blank=True,
                        null=True,
                        help_text="Full traceback at time of final failure",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="failed_job_dlq_entries",
                        to="tenants.tenant",
                        help_text="Tenant the job belonged to",
                    ),
                ),
                (
                    "retry_count",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of times this DLQ entry has been retried",
                    ),
                ),
                (
                    "resolved_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="When this entry was resolved (retried successfully or purged)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
            ],
            options={
                "db_table": "failed_job_dlq",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["tenant", "created_at"],
                        name="dlq_tenant_created_idx",
                    ),
                    models.Index(
                        fields=["resolved_at"],
                        name="dlq_resolved_idx",
                    ),
                    models.Index(
                        fields=["queue", "created_at"],
                        name="dlq_queue_created_idx",
                    ),
                ],
            },
        ),
    ]
