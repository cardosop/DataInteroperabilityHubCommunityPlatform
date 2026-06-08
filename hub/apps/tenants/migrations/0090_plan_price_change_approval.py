"""285.13.9.3 -- add ``PlanPriceChangeApproval`` model for two-person
approval on plan price changes exceeding $1,000/mo (100000 cents).

Follows the same pattern as ``FeatureFlagFlipApproval`` (Phase 235.1).
"""

import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenants", "0089_tier_profile_and_limit_dimension"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanPriceChangeApproval",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True, default=uuid.uuid4, editable=False, serialize=False
                    ),
                ),
                (
                    "old_price_cents",
                    models.IntegerField(
                        help_text="Current price_amount_cents before the change.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "new_price_cents",
                    models.IntegerField(
                        help_text="Proposed price_amount_cents after approval.",
                        validators=[django.core.validators.MinValueValidator(0)],
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
                ("reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_price_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requested_price_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_change_approvals",
                        to="tenants.tenantplan",
                    ),
                ),
            ],
            options={
                "db_table": "plan_price_change_approvals",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="planpricechangeapproval",
            index=models.Index(
                fields=["tenant_plan", "status"],
                name="ppca_plan_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="planpricechangeapproval",
            index=models.Index(
                fields=["status", "created_at"],
                name="ppca_status_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="planpricechangeapproval",
            constraint=models.UniqueConstraint(
                fields=["tenant_plan"],
                condition=models.Q(status="PENDING"),
                name="one_pending_price_change_per_plan",
            ),
        ),
    ]
