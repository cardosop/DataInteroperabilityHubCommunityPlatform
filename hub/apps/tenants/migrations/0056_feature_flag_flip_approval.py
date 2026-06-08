"""Phase 235.1.4 — ``FeatureFlagFlipApproval`` table for the two-person rule."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0055_tenant_webhook_outbound_rate_limit_per_minute"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureFlagFlipApproval",
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
                    "flag",
                    models.CharField(
                        help_text=(
                            "Name of the ``Tenant.<flag>_enabled`` BooleanField the request "
                            "wants to flip. MUST be a name registered in "
                            ":mod:`hub.apps.tenants.feature_flag_registry` with "
                            "``sensitive=True``."
                        ),
                        max_length=128,
                    ),
                ),
                (
                    "requested_value",
                    models.BooleanField(
                        help_text=(
                            "The new value the requester wants the flag to take. Stored "
                            "explicitly so an auditor can replay intent even if the live "
                            "tenant value drifts between request and approval."
                        ),
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("EXPIRED", "Expired"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "reason",
                    models.TextField(
                        help_text=(
                            "Free-text justification (min 10 chars enforced at the API "
                            "layer). Pinned in the meta-audit so the regulator can read "
                            "WHY a sensitive flag was flipped."
                        ),
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Second PLATFORM_ADMIN who approved the request. MUST be "
                            "different from ``requested_by``."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_feature_flag_flips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        help_text="PLATFORM_ADMIN who opened the request.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requested_feature_flag_flips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant the flag flip targets.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feature_flag_flip_approvals",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "feature_flag_flip_approvals",
                "ordering": ["-requested_at"],
            },
        ),
        migrations.AddIndex(
            model_name="featureflagflipapproval",
            index=models.Index(
                fields=["tenant", "flag", "status"],
                name="ffa_tenant_flag_status_ix",
            ),
        ),
        migrations.AddIndex(
            model_name="featureflagflipapproval",
            index=models.Index(
                fields=["status", "requested_at"],
                name="ffa_status_requested_ix",
            ),
        ),
        migrations.AddConstraint(
            model_name="featureflagflipapproval",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "PENDING")),
                fields=("tenant", "flag"),
                name="ffa_one_pending_per_tenant_flag",
            ),
        ),
    ]
