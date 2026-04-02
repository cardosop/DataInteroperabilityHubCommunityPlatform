"""
Re-create IngestionTemplate model.

Migration 0005 dropped the ingestion_templates table but the Python model
was kept in templates.py. This migration re-creates the table so that the
model and database are back in sync.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from hub.apps.scheduled_ingestion.models import ScheduleType, SourceType


class Migration(migrations.Migration):

    dependencies = [
        ("scheduled_ingestion", "0009_encrypt_source_config"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestionTemplate",
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
                    "name",
                    models.CharField(
                        help_text="Template name",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Template description",
                        null=True,
                    ),
                ),
                (
                    "template_type",
                    models.CharField(
                        help_text="Template type (e.g., 'S3_DAILY_FILES', 'API_POLLING', 'DATABASE_REPLICATION')",
                        max_length=50,
                    ),
                ),
                (
                    "is_system_template",
                    models.BooleanField(
                        default=False,
                        help_text="True if this is a system-wide template (available to all tenants)",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=SourceType.choices,
                        help_text="Source type for this template",
                        max_length=50,
                    ),
                ),
                (
                    "source_config_template",
                    models.JSONField(
                        help_text="Source configuration template with placeholders",
                    ),
                ),
                (
                    "schedule_type",
                    models.CharField(
                        choices=ScheduleType.choices,
                        default=ScheduleType.DAILY,
                        help_text="Default schedule type",
                        max_length=20,
                    ),
                ),
                (
                    "schedule_config_template",
                    models.JSONField(
                        help_text="Schedule configuration template",
                    ),
                ),
                (
                    "file_pattern_template",
                    models.CharField(
                        help_text="File pattern template",
                        max_length=255,
                    ),
                ),
                (
                    "ingestion_config_template",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Ingestion configuration template",
                        null=True,
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
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who created the template",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_ingestion_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        help_text="Tenant this template belongs to (null for system-wide templates)",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingestion_templates",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "ingestion_templates",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["tenant", "template_type"],
                        name="ingestion_te_tenant__idx",
                    ),
                    models.Index(
                        fields=["is_system_template", "template_type"],
                        name="ingestion_te_is_syst_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("tenant__isnull", False)),
                        fields=["tenant", "name"],
                        name="unique_template_name_per_tenant",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_system_template", True)),
                        fields=["name"],
                        name="unique_system_template_name",
                    ),
                ],
            },
        ),
    ]
