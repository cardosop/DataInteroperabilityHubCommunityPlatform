"""Phase 235.4.1 + 235.4.2 — Impersonation tenant fields + ImpersonationSession.

Schema-only changes (one logical migration so the deploy stays atomic):

* ``Tenant.impersonation_allowed`` (BooleanField, default False) — per-tenant
  master switch for the PLATFORM_ADMIN impersonation feature.
* ``Tenant.impersonation_default_max_minutes`` (PositiveIntegerField,
  default 60, bounded [5, 240]) — per-tenant default cap for a new
  impersonation session.
* NEW ``ImpersonationSession`` table — see ``models.py`` for the full
  contract; tracks the live ACTIVE/ENDED state of an operator's
  impersonation of a target user.

The new table is row-level-security-paired via
``0060_enable_rls_impersonation_session.py`` (next migration). The two
tenant fields are columns on the existing ``tenants`` table which is the
RLS boundary itself, so no paired RLS is required for them.
"""
import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0058_tenant_scheduled_for_deletion_and_legal_hold"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="impersonation_allowed",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 235.4 — when True, PLATFORM_ADMIN may impersonate "
                    "users in this tenant via "
                    "``POST /api/v1/admin/impersonate/``. Default False so the "
                    "deploy does not silently grant the capability; ops flips "
                    "per tenant after explicit customer authorisation."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="impersonation_default_max_minutes",
            field=models.PositiveIntegerField(
                default=60,
                validators=[
                    django.core.validators.MinValueValidator(5),
                    django.core.validators.MaxValueValidator(240),
                ],
                help_text=(
                    "Phase 235.4 — per-tenant default max-minutes for a new "
                    "impersonation session. Hard cap is 240; the endpoint "
                    "rejects callers that override above the cap with HTTP "
                    "400 ``MAX_MINUTES_OUT_OF_RANGE``."
                ),
            ),
        ),
        migrations.CreateModel(
            name="ImpersonationSession",
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
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ENDED", "Ended")],
                        db_index=True,
                        default="ACTIVE",
                        help_text="ACTIVE or ENDED.",
                        max_length=20,
                    ),
                ),
                (
                    "max_minutes",
                    models.PositiveIntegerField(
                        help_text=(
                            "Operator-chosen (or tenant-default) duration cap "
                            "in minutes. The hard cap is 240 (enforced at the "
                            "endpoint); values above the cap are rejected with "
                            "HTTP 400 MAX_MINUTES_OUT_OF_RANGE."
                        )
                    ),
                ),
                (
                    "reason",
                    models.TextField(
                        help_text=(
                            "Operator justification (min 10 chars enforced "
                            "at the API layer). Pinned in the audit trail so "
                            "an auditor can read WHY the session was opened."
                        )
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "end_reason",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="``manual_exit`` or ``expired``.",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "impersonator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="impersonation_sessions_started",
                        to=settings.AUTH_USER_MODEL,
                        help_text="The PLATFORM_ADMIN who opened the session.",
                    ),
                ),
                (
                    "impersonated_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_sessions_as_target",
                        to=settings.AUTH_USER_MODEL,
                        help_text="The user whose identity is being assumed.",
                    ),
                ),
                (
                    "impersonator_tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="impersonation_sessions_outbound",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "impersonated_tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_sessions_inbound",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "impersonation_sessions",
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="impersonationsession",
            index=models.Index(
                fields=["impersonator"],
                name="imp_sess_impr_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="impersonationsession",
            index=models.Index(
                fields=["impersonated_user"],
                name="imp_sess_target_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="impersonationsession",
            index=models.Index(
                fields=["impersonated_tenant", "status"],
                name="imp_sess_tt_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="impersonationsession",
            index=models.Index(
                fields=["status", "expires_at"],
                name="imp_sess_status_exp_idx",
            ),
        ),
    ]
