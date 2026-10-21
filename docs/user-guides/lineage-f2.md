# Lineage F2 — Field-level mapping editor

**Audience:** Data product owners, contract editors
**Capability flag:** `lineage.field_level_mapping`

## What it does

Field-level lineage editor lets you map source fields → target
fields visually instead of editing the raw `hub_contract_json.lineage`
subtree. Each mapping captures the source contract / model / field
on one side and the target contract / model / field on the other.

## How to use

1. Open a contract → **Lineage** tab.
2. Toggle "Show fields" to expand each contract node into per-field
   sub-nodes.
3. Drag a connection from a source field to a target field.
4. Optionally set `transformation_ref` (e.g. dbt model id) +
   `job_ref` (e.g. Airflow run id).
5. Save — the contract's `hub_contract_json.lineage.contracts` is
   updated atomically; the relational `LineageEdge` index updates
   via the post-save signal.

## Notes

- The editor uses an If-Match ETag header for concurrency — if
  another user saved between your load and save, you get a clear
  "edited by someone else" prompt.
- An optional `Idempotency-Key` header dedupes 24-hour replays.

## Related

- [Lineage extraction reference](../adr/lineage/ADR-LIN-002.md)
- [Support FAQ](../support/lineage-faq.md)
