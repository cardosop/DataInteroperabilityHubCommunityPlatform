# Phase 228.F3.4 (REQ-LIN-F3-002) — additive-only:
# CreateModel LineageSubscription (per-user opt-in for lineage-impact
# notifications) + DB-level XOR + UNIQUE constraints.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0026_lineage_edge_archive"),
        ("assets", "0011_asset_metadata_json"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LineageSubscription",
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
                    "severity_threshold",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("CRITICAL", "Critical"),
                        ],
                        default="HIGH",
                        max_length=16,
                    ),
                ),
                ("in_app", models.BooleanField(default=True)),
                ("email", models.BooleanField(default=False)),
                ("slack", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("last_dispatched_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source_asset",
                    models.ForeignKey(
                        blank=True,
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lineage_subscriptions",
                        to="assets.asset",
                    ),
                ),
                (
                    "source_contract",
                    models.ForeignKey(
                        blank=True,
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lineage_subscriptions",
                        to="contracts.contract",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lineage_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Lineage Subscription",
                "verbose_name_plural": "Lineage Subscriptions",
                "db_table": "contracts_lineage_subscription",
            },
        ),
        migrations.AddConstraint(
            model_name="lineagesubscription",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(source_contract__isnull=False, source_asset__isnull=True)
                    | models.Q(source_contract__isnull=True, source_asset__isnull=False)
                ),
                name="lineage_sub_xor_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="lineagesubscription",
            constraint=models.UniqueConstraint(
                fields=("user", "source_contract", "source_asset"),
                name="lineage_sub_unique_user_source",
            ),
        ),
        migrations.AddIndex(
            model_name="lineagesubscription",
            index=models.Index(
                fields=["user", "created_at"],
                name="lin_sub_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lineagesubscription",
            index=models.Index(
                fields=["source_contract", "severity_threshold"],
                name="lin_sub_contract_sev_idx",
            ),
        ),
    ]
