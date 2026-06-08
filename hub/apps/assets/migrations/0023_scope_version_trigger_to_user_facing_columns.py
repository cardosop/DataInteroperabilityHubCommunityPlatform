"""
Scope assets_force_version_increment_trg to user-facing columns only.

The BEFORE UPDATE trigger on the assets table unconditionally bumped
``version`` on every UPDATE (migration 0017). Background processes
(compliance scans, DQ runs, search-vector rebuilds, health-score
recalculation, view/download counters) each touch a single derived
column on the asset row. Every such UPDATE incremented ``version``,
invalidating the optimistic-lock token the SPA fetched on page load.

By the time the user clicked Activate / Retire / Save, the DB had
already bumped ``version`` one or more times — producing a persistent
409 CONCURRENT_MODIFICATION that retries could never outrun.

The fix scopes the trigger to user-initiated column changes only.
When ONLY background columns change (dq_status, compliance_status,
semantic_status, health_score, popularity_score, view_count,
download_count, search_vector, updated_at), the version stays the
same so the user's optimistic-lock token remains valid.
"""
from django.db import migrations


_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION assets_force_version_increment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Only bump version when a user-facing column actually changed.
    -- Background / derived columns that are updated by async workers
    -- (compliance scans, DQ runs, search-vector rebuilds, health-score
    -- recalculation, view/download counters) must NOT invalidate the
    -- optimistic-lock token the SPA holds.
    IF NEW.name               IS DISTINCT FROM OLD.name
    OR NEW.key                IS DISTINCT FROM OLD.key
    OR NEW.description        IS DISTINCT FROM OLD.description
    OR NEW.domain             IS DISTINCT FROM OLD.domain
    OR NEW.status             IS DISTINCT FROM OLD.status
    OR NEW.metadata_json      IS DISTINCT FROM OLD.metadata_json
    OR NEW.source_type        IS DISTINCT FROM OLD.source_type
    OR NEW.source_metadata    IS DISTINCT FROM OLD.source_metadata
    OR NEW.data_strategy      IS DISTINCT FROM OLD.data_strategy
    OR NEW.categories_of_subjects IS DISTINCT FROM OLD.categories_of_subjects
    OR NEW.recipient_categories   IS DISTINCT FROM OLD.recipient_categories
    OR NEW.warehouse_connection_id IS DISTINCT FROM OLD.warehouse_connection_id
    OR NEW.semantic_federate_optout IS DISTINCT FROM OLD.semantic_federate_optout
    THEN
        NEW.version := COALESCE(OLD.version, 0) + 1;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS
    assets_force_version_increment_trg
ON assets;
CREATE TRIGGER assets_force_version_increment_trg
BEFORE UPDATE ON assets
FOR EACH ROW
EXECUTE FUNCTION assets_force_version_increment();
"""

_REVERSE_SQL = """
CREATE OR REPLACE FUNCTION assets_force_version_increment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.version := COALESCE(OLD.version, 0) + 1;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS
    assets_force_version_increment_trg
ON assets;
CREATE TRIGGER assets_force_version_increment_trg
BEFORE UPDATE ON assets
FOR EACH ROW
EXECUTE FUNCTION assets_force_version_increment();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0022_alter_asset_data_strategy"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_TRIGGER_SQL,
            reverse_sql=_REVERSE_SQL,
        ),
    ]
