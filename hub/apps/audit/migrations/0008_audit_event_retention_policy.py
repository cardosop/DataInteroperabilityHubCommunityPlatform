"""Phase 234.5.1 — per-event-type audit retention override table."""
import uuid

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0007_chain_index_concurrent"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEventRetentionPolicy",
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
                    "event_type",
                    models.CharField(
                        help_text=(
                            "AuditEvent.action value this row overrides "
                            "(e.g. ``DSAR_SUBMITTED``, ``BREACH_INCIDENT_OPENED``). "
                            "Matched verbatim against the persisted ``action`` column."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "retention_days",
                    models.IntegerField(
                        blank=True,
                        help_text=(
                            "Days an event of this type is kept before archival. "
                            "Auto-populated from ``regulation_keys`` when those are "
                            "provided; otherwise must be set explicitly."
                        ),
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "regulation_keys",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=64),
                        blank=True,
                        default=list,
                        help_text=(
                            "Uppercase regime tokens (e.g. ``[\"GDPR\", \"UK_GDPR\"]``). "
                            "When non-empty, ``retention_days`` is derived from "
                            "``data_retention_period_days_for_regime_keys``."
                        ),
                        size=None,
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "When False, this row is ignored by the resolver — useful "
                            "for staging a regime change without deleting history."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who created this override (nullable for system seeds).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_audit_event_retention_policies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        help_text="Tenant this override applies to (per-tenant scoping).",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_event_retention_policies",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "audit_event_retention_policies",
                "ordering": ["tenant_id", "event_type"],
            },
        ),
        migrations.AddIndex(
            model_name="auditeventretentionpolicy",
            index=models.Index(
                fields=["tenant", "enabled"],
                name="audit_evt_ret_tenant_en_ix",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditeventretentionpolicy",
            constraint=models.UniqueConstraint(
                fields=("tenant", "event_type"),
                name="audit_evt_ret_tenant_evt_uniq",
            ),
        ),
    ]
