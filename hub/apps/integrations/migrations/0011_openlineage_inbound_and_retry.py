# Phase 228 F4 (DoD self-audit GAP-D4 + GAP-D9) — additive-only:
# * AddField next_retry_at on OpenLineageDeadLetter
# * CreateModel OpenLineageInboundEvent (idempotency cache for inbound)
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0010_openlineage"),
        ("tenants", "0023_add_archival_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="openlineagedeadletter",
            name="next_retry_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    "Earliest time the replay sweep will re-try this row. "
                    "NULL = ready immediately (initial DLQ insert). The sweep "
                    "filters ``next_retry_at__isnull=True OR next_retry_at <= NOW()``."
                ),
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="OpenLineageInboundEvent",
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
                    "event_id",
                    models.CharField(
                        db_index=True,
                        help_text="OpenLineage ``run.runId`` — the idempotency key.",
                        max_length=255,
                    ),
                ),
                (
                    "edges_created",
                    models.IntegerField(
                        default=0,
                        help_text=(
                            "Number of LineageEdge rows the first-accept created. "
                            "Returned in the duplicate-POST 202 response so the "
                            "original-vs-duplicate semantics are byte-identical."
                        ),
                    ),
                ),
                (
                    "accepted_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="openlineage_inbound_events",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "OpenLineage Inbound Event",
                "verbose_name_plural": "OpenLineage Inbound Events",
                "db_table": "openlineage_inbound_event",
                "ordering": ["-accepted_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="openlineageinboundevent",
            constraint=models.UniqueConstraint(
                fields=("tenant", "event_id"),
                name="ol_inbound_tenant_eventid_uq",
            ),
        ),
        migrations.AddIndex(
            model_name="openlineageinboundevent",
            index=models.Index(
                fields=["tenant", "accepted_at"],
                name="ol_inbound_tenant_time_idx",
            ),
        ),
    ]
