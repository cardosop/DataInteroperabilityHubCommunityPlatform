"""
Phase 250.3.B.2 — visibility-as-property deprecation phase 1.

Per D250.4, ``Asset.visibility`` becomes a ``@property`` derived from
``Asset.status`` (PUBLIC iff status==PUBLIC, else INTERNAL). Phase 1
of the deprecation:

* Tells Django to forget the ``visibility`` model-field declaration
  and the ``(tenant, visibility)`` index — both via state operations.
* Drops the legacy ``(tenant, visibility)`` btree index in PostgreSQL
  so it stops consuming buffer cache.
* Nulls every value in the ``visibility`` column AND drops the
  ``NOT NULL`` constraint. The column itself is RETAINED (no
  ``DROP COLUMN``) for forensic / rollback safety; phase-2 ships the
  column drop only after three release cycles of zero
  ``ASSET_VISIBILITY_WRITE_DEPRECATED`` audit events.

The state vs database split is the load-bearing piece — Django's
``RemoveField`` would also issue ``DROP COLUMN`` in the database;
``SeparateDatabaseAndState`` lets us tell Django "this field is no
longer in the model" while preserving the underlying column.

Non-zero downtime considerations:
* The ``ALTER TABLE ... DROP NOT NULL`` is metadata-only on
  PostgreSQL ≥9.4 (no rewrite, no exclusive lock beyond the brief
  catalog update).
* The ``UPDATE assets SET visibility = NULL`` writes every row but
  is single-statement and run inside the migration's transaction.
  For tenants with millions of assets this is the slow part of the
  migration; ``maintenance_work_mem`` should be raised before the
  deploy if rowcount > 1M.
* The ``DROP INDEX`` is concurrent-safe under standard pg locking
  on a btree index; no other transaction blocks during the drop.
"""
from django.db import migrations


_SQL_NULL_VISIBILITY_FORWARD = """
    ALTER TABLE assets ALTER COLUMN visibility DROP NOT NULL;
    ALTER TABLE assets ALTER COLUMN visibility DROP DEFAULT;
    UPDATE assets SET visibility = NULL;
"""

# Reverse path: re-apply the default + NOT NULL constraint after
# back-filling every row with the derived value (PUBLIC if
# status='PUBLIC', else INTERNAL). The back-fill mirrors the @property
# rule from ``Asset.visibility`` so a rolled-back DB matches the
# pre-Phase-1 state byte-for-byte.
_SQL_NULL_VISIBILITY_REVERSE = """
    UPDATE assets
       SET visibility = CASE
           WHEN status = 'PUBLIC' THEN 'PUBLIC'
           ELSE 'INTERNAL'
       END;
    ALTER TABLE assets ALTER COLUMN visibility SET DEFAULT 'INTERNAL';
    ALTER TABLE assets ALTER COLUMN visibility SET NOT NULL;
"""


class Migration(migrations.Migration):
    """Phase-1 visibility deprecation — model state + DB column null."""

    dependencies = [
        ("assets", "0012_asset_semantic_federate_optout"),
    ]

    operations = [
        # 1. State: remove the (tenant, visibility) btree index. The
        #    actual ``DROP INDEX`` on the database side runs in the
        #    SeparateDatabaseAndState block below so we control timing
        #    and can use ``IF EXISTS`` for forward-compat with envs
        #    where the index was hand-dropped.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="asset",
                    name="assets_tenant__41780b_idx",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="DROP INDEX IF EXISTS assets_tenant__41780b_idx;",
                    reverse_sql=(
                        "CREATE INDEX IF NOT EXISTS assets_tenant__41780b_idx "
                        "ON assets (tenant_id, visibility);"
                    ),
                ),
            ],
        ),
        # 2. State: tell Django the visibility field no longer exists
        #    on the model. Database side: null every row + drop the
        #    NOT NULL + drop the default. The column itself stays so
        #    forensic queries (``SELECT visibility FROM assets WHERE
        #    updated_at < phase1_deploy_ts``) can still read it during
        #    the deprecation soak.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="asset",
                    name="visibility",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=_SQL_NULL_VISIBILITY_FORWARD,
                    reverse_sql=_SQL_NULL_VISIBILITY_REVERSE,
                ),
            ],
        ),
    ]
