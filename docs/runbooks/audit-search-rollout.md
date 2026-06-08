# Audit FTS Rollout Runbook (Phase 234.6)

This runbook covers the rollout of the per-row `details_json_tsvector`
Postgres FTS column on `audit_events` and the companion GIN index.

The implementation lives in:

- Schema migration: [`hub/apps/audit/migrations/0010_audit_event_details_tsvector.py`](../../hub/apps/audit/migrations/0010_audit_event_details_tsvector.py)
- Concurrent GIN index: [`hub/apps/audit/migrations/0011_audit_event_tsvector_index_concurrent.py`](../../hub/apps/audit/migrations/0011_audit_event_tsvector_index_concurrent.py)
- API surface: [`hub/apps/audit/views.py`](../../hub/apps/audit/views.py) `AuditEventViewSet.get_queryset` (the `?q=` branch)
- Latency metric: [`hub/apps/audit/metrics.py`](../../hub/apps/audit/metrics.py)

## Pre-deploy checklist

### 1. Row count gate (AUDIT.1)

`ALTER TABLE audit_events ADD COLUMN details_json_tsvector tsvector GENERATED ALWAYS AS (...) STORED;`
rewrites the **entire table** to materialise the new column. The
operation takes an `ACCESS EXCLUSIVE` lock for the duration of the
rewrite. We have empirically validated this is acceptable up to ~50M
rows in a standard 4-vCPU primary; beyond that the rewrite exceeds a
20-minute deploy window and starts to risk replication lag tripping
the read-replica monitor.

Before deploying migration `0010`:

```sql
-- on the staging mirror (or read-replica) of production:
SELECT count(*) FROM audit_events;
```

- **< 50,000,000 rows**: ship `0010` + `0011` together. Default path.
- **≥ 50,000,000 rows**: follow the **Large-table contingency** section below.

### 2. Postgres version

The `GENERATED ALWAYS AS (...) STORED` syntax requires Postgres ≥ 12.
The hub's RDS minor-version pin must reflect this — re-verify with:

```sql
SHOW server_version;
```

### 3. Available disk

`audit_events_details_tsv_gin` is a GIN index over a tsvector column.
On a 50M-row table the index is empirically ~3–5 GB. Confirm the
database volume has at least 10 GB free before launching migration
`0011` (the index build itself needs scratch space).

## Standard deploy (≤ 50M rows)

```bash
# Both migrations in one deploy:
python hub/manage.py migrate audit
```

Migration `0010` takes an `ACCESS EXCLUSIVE` lock briefly during the
table rewrite (every existing row is read once + the new column
populated). Migration `0011` is `atomic = False` + `CREATE INDEX
CONCURRENTLY` — it does NOT block writes.

Post-deploy verification:

```sql
-- 1. Column exists and is populated:
SELECT count(*) FROM audit_events WHERE details_json_tsvector IS NOT NULL;
-- Should equal total row count.

-- 2. Index exists and is valid:
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'audit_events'
  AND indexname = 'audit_events_details_tsv_gin';

-- 3. Index is being used:
EXPLAIN ANALYZE
SELECT id FROM audit_events
WHERE tenant_id = '<some-tenant>'
  AND details_json_tsvector @@ websearch_to_tsquery('english', 'test');
-- Plan should show: "Bitmap Index Scan on audit_events_details_tsv_gin"
```

Smoke-test the SPA: open Audit Log → type a term in the new search box.
Latency should be ~50–500 ms on a warm cache.

## Large-table contingency (≥ 50M rows)

When the row count gate above trips, the standard
`ALTER TABLE ADD COLUMN ... GENERATED ALWAYS AS (...) STORED` is NOT
viable: it rewrites every row inside one `ACCESS EXCLUSIVE` lock and
would exceed the deploy window.

**Important:** Postgres does NOT support converting an existing
populated column into a STORED GENERATED column. `ALTER COLUMN ...
ADD GENERATED ALWAYS AS (expression) STORED` is invalid syntax — the
only `ADD GENERATED` form Postgres accepts is for IDENTITY columns.
The only ways to end up with a GENERATED column on an existing table
are (a) the original `ADD COLUMN GENERATED` (a full table rewrite,
which is what we're trying to avoid), or (b) `DROP COLUMN` followed
by re-`ADD COLUMN GENERATED` (also a full table rewrite — same
constraint).

Therefore, for ≥ 50M-row tables the runbook recommends abandoning
the GENERATED column shape entirely and using a
**trigger-maintained regular `tsvector` column** instead. The
externally-visible behaviour — column exists, populated, indexed by
GIN, queried via `@@ websearch_to_tsquery` — is identical; only the
maintenance mechanism differs. The application code, including the
Django ORM and `AuditEventViewSet.list`'s `?q=` path, does not need
to change.

The trigger path requires a one-off custom migration; do NOT apply
`0010_audit_event_details_tsvector` on these clusters (its model
state declares a `GeneratedField` which mismatches a
trigger-maintained column — see the **Django state-sync caveat**
at the bottom of this section).

### Deploy A — nullable column

Apply a custom migration that adds the column as a plain
`tsvector NULL` (NOT `GENERATED`):

```sql
ALTER TABLE audit_events ADD COLUMN details_json_tsvector tsvector;
```

This takes only the catalog lock — milliseconds, no rewrite. No
backfill yet.

### Deploy B — chunked backfill

Run a one-off script (NOT in a migration; outside the deploy window)
that populates the column in 10k-row batches:

```sql
WITH batch AS (
  SELECT id FROM audit_events
  WHERE details_json_tsvector IS NULL
  ORDER BY id LIMIT 10000 FOR UPDATE SKIP LOCKED
)
UPDATE audit_events ae
SET details_json_tsvector =
    setweight(to_tsvector('english',
        translate(coalesce(ae.action, ''), '_', ' ')), 'A')
 || setweight(to_tsvector('english',
        translate(coalesce(ae.resource_type, ''), '_', ' ')), 'B')
 || setweight(jsonb_to_tsvector('english',
        coalesce(ae.details_json, '{}'::jsonb), '"all"'), 'C')
FROM batch
WHERE ae.id = batch.id;
```

> Note: `translate(action, '_', ' ')` matches the expression in
> `0010_audit_event_details_tsvector.py` exactly. Audit-action
> identifiers (`ASSET_CREATED`, `COMPLIANCE_RUN_CREATED`, …) tokenise
> as the two/three lexemes operators expect to type in the search
> box; Postgres's default `english` parser treats `_` as a word
> character and would otherwise produce a single unsplit lexeme.

Loop until `WHERE details_json_tsvector IS NULL` returns zero rows.
Throttle to keep replica lag below your alert threshold.

Run the GIN index build (`CONCURRENTLY`) once the backfill is done —
this is `0011_audit_event_tsvector_index_concurrent` unchanged from
the standard path.

### Deploy C — install the maintenance trigger

A BEFORE INSERT/UPDATE trigger reproduces the GENERATED expression on
every write. This is the only sustainable mechanism that side-steps
the table rewrite — the trigger fires per-row so it has no
table-level lock impact:

```sql
CREATE OR REPLACE FUNCTION audit_events_tsvector_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.details_json_tsvector :=
        setweight(to_tsvector('english',
            translate(coalesce(NEW.action, ''), '_', ' ')), 'A')
     || setweight(to_tsvector('english',
            translate(coalesce(NEW.resource_type, ''), '_', ' ')), 'B')
     || setweight(jsonb_to_tsvector('english',
            coalesce(NEW.details_json, '{}'::jsonb), '"all"'), 'C');
    RETURN NEW;
END;
$$;

CREATE TRIGGER audit_events_tsvector_update
BEFORE INSERT OR UPDATE OF action, resource_type, details_json
ON audit_events
FOR EACH ROW EXECUTE FUNCTION audit_events_tsvector_trigger();
```

The function body MUST stay byte-identical to the standard-path
GENERATED expression — any drift would mean rows written via the
trigger path index differently from rows written via the GENERATED
path. Treat it as a code-review invariant.

### Django state-sync caveat

The standard-path migration `0010_audit_event_details_tsvector.py`
adds a `GeneratedField` to the model state. On a trigger-maintained
cluster, that state is a *lie* — the actual column is regular. The
ORM still works correctly because reads only need `output_field` for
lookup resolution (`SearchQuery` → `@@`), and writes are excluded by
`GeneratedField.generated=True`. The trigger handles writes that
Django thinks aren't happening.

If `makemigrations` is later run against a working-copy connected to
a trigger-maintained cluster, Django will not detect any drift — the
model and state already declare the `GeneratedField`. The trigger is
invisible to Django introspection. Document this divergence in the
cluster's `terraform/migration-state.md` so a future engineer
debugging "why doesn't this column rewrite when I edit the
expression" lands on this runbook.

## Operational notes

### Slow-query alert

[`hub/apps/audit/metrics.py`](../../hub/apps/audit/metrics.py) exposes
`audit_search_query_duration_seconds` (histogram, label `tenant_id`).
The standard on-call alert:

```promql
histogram_quantile(0.95,
  sum by (le) (rate(audit_search_query_duration_seconds_bucket[5m]))
) > 5
for: 5m
```

Triage:

1. Check `pg_stat_user_indexes` for `idx_scan` on
   `audit_events_details_tsv_gin` — a sudden drop means the planner
   is preferring a sequential scan (statistics drift; run `ANALYZE
   audit_events`).
2. Check GIN index size growth: `\di+` should show stable size per
   tenant audit volume. If the index has bloated > 2× expected,
   schedule `REINDEX INDEX CONCURRENTLY audit_events_details_tsv_gin`
   off-peak.
3. Check long-running queries (`pg_stat_activity` where `query LIKE
   '%details_json_tsvector%'`) — a single tenant with a malformed
   query may dominate. Per-tenant cardinality on the label lets
   Grafana surface this with a `topk(5, ...)` panel.

### Tenant scoping (AUDIT.3)

The viewset's `get_queryset` ANDs the `?q=` filter AFTER the existing
tenant scope. There is no code path where a search request can return
another tenant's rows. The contract is pinned by
`test_audit_search.py::TestAuditFtsApi::test_q_param_tenant_scoping_blocks_cross_tenant_matches`.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
