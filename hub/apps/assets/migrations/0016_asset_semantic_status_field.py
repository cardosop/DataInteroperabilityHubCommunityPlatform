"""
Phase 250.7.A.1 — semantic-mapping + search-indexing status field.

Adds ``Asset.semantic_status`` (CharField choices UNKNOWN / PASS /
WARN / FAIL, default UNKNOWN). Per D250.6, semantic / search
failures during activation are observability events, not gates —
the asset still ACTIVATES on degradation and this column is the
durable signal for the SPA's ``SemanticDegradedBanner``.

Default UNKNOWN is the load-bearing choice: pre-existing assets
created before this migration shipped have no recorded semantic /
search status, and stamping them as PASS would lie (we haven't
verified) while stamping them as FAIL would falsely page operators
on every existing asset. UNKNOWN says "we haven't checked yet" —
the SPA's banner code can branch on UNKNOWN to render nothing
(don't show a banner for assets we have no data on) vs. FAIL
(active, render the degradation banner with retry CTA).

Migration safety:
* ``AddField`` with a default — PostgreSQL stamps every existing
  row with the default UNKNOWN value in a single ``ALTER TABLE``
  metadata-only operation (PG ≥11 fast-default optimisation; no
  row rewrite).
* No new index — queries on ``semantic_status`` are diagnostic /
  ad-hoc (operator dashboards) and don't need an index. If a
  per-tenant ``semantic_status=FAIL`` filter becomes hot, a
  follow-up migration adds the index (cheap, non-blocking on PG).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0015_external_resource_consumer_deleted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="semantic_status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("UNKNOWN", "Unknown"),
                    ("PASS", "Pass"),
                    ("WARN", "Warning"),
                    ("FAIL", "Fail"),
                ],
                default="UNKNOWN",
                help_text=(
                    "Phase 250.7.A — semantic-mapping + search-"
                    "indexing status: UNKNOWN (default; not yet "
                    "checked), PASS (both succeeded), WARN "
                    "(partial degradation reserved for future "
                    "granular failures), FAIL (one or both "
                    "failed; asset is ACTIVE but not discoverable "
                    "in semantic search)."
                ),
            ),
        ),
    ]
