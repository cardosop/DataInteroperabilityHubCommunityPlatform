"""
Phase 240.1.A.3 — composite index on (tenant_id, id, last_alert_id) for
the dedup lookup, deployed with ``CONCURRENTLY`` to avoid a SHARE
lock against ``dq_alerting_rules`` during deploy.

Per D240.5 this MUST be a separate migration with ``atomic = False`` —
PostgreSQL refuses ``CREATE INDEX CONCURRENTLY`` inside an explicit
transaction (which is what Django wraps each migration in by default).

Critical correctness note: ``migrations.AddIndex`` issues a plain
``CREATE INDEX`` even when ``atomic = False`` is set on the migration —
``atomic=False`` only opts the migration OUT of the per-migration
transaction; it does NOT change the SQL Django emits. To get
``CREATE INDEX CONCURRENTLY`` we MUST use Django's
``django.contrib.postgres.operations.AddIndexConcurrently``. Using
the plain ``AddIndex`` here would still take a SHARE lock during
deploy, blocking the dispatcher's ``UPDATE dq_alerting_rules SET
last_fired_at = ...`` calls — exactly the deploy-time hazard
240.1.A.3 was meant to avoid.

The dedup query is::

    SELECT 1 FROM dq_alerting_rules
    WHERE tenant_id = ? AND id = ? AND last_alert_id = ?

so the column order matches the most-selective-first rule:

    1. tenant_id  — filters out other tenants
    2. id         — single row in practice
    3. last_alert_id — equality probe (short-circuit on no-match)

``last_alert_id`` is a 32-char hex string so the b-tree index entry
is small (<48 bytes) and effectively read-only on a per-rule basis.
"""
from __future__ import annotations

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Atomic=False is required for CONCURRENTLY index creation."""

    atomic = False

    dependencies = [
        ("dq", "0006_alerting_dedupe_fields"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="dqalertingrule",
            index=models.Index(
                fields=["tenant", "id", "last_alert_id"],
                name="dq_alerting_dedup_idx",
            ),
        ),
    ]
