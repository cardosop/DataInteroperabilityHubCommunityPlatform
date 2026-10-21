# Phase 223.1 — In-app notification inbox
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_add_transformation_email_types"),
        ("audit", "0002_alter_auditevent_options_and_more"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserNotification",
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
                ("title", models.CharField(max_length=200)),
                ("message", models.TextField()),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("INFO", "Info"),
                            ("SUCCESS", "Success"),
                            ("WARNING", "Warning"),
                            ("ERROR", "Error"),
                        ],
                        default="INFO",
                        max_length=10,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("GOVERNANCE", "Governance"),
                            ("MARKETPLACE", "Marketplace"),
                            ("JOBS", "Jobs"),
                            ("CONTRACTS", "Contracts"),
                            ("SYSTEM", "System"),
                        ],
                        default="SYSTEM",
                        max_length=20,
                    ),
                ),
                (
                    "resource_type",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("resource_id", models.UUIDField(blank=True, null=True)),
                ("read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "audit_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_notifications",
                        to="audit.auditevent",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_notifications",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "user_notifications",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "read", "-created_at"],
                        name="user_notif_user_read_idx",
                    ),
                    models.Index(
                        fields=["tenant", "-created_at"],
                        name="user_notif_tenant_idx",
                    ),
                ],
            },
        ),
    ]
