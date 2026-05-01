# Lineage F5 — Time-travel + diff

**Audience:** Data product owners, auditors
**Capability flag:** `lineage.snapshots`

## What it does

Two new controls above the Lineage graph:

- **As of** date picker — render the lineage at any historical
  instant (within the 12-month hot retention window; older points
  trigger an archive read).
- **Version** dropdown — pick a contract version; the graph
  re-renders at that version's `created_at`.

Plus a **diff** view that compares two anchors and surfaces three
buckets:

- **Added** (green, `+` glyph) — edges that exist at `to` but not
  at `from`.
- **Removed** (red, `−` glyph) — edges that existed at `from` but
  not at `to`.
- **Unchanged** (gray, `=` glyph) — edges identical at both anchors.

The `modified` bucket is intentionally always empty: under SCD-2
close-and-reopen, a transformation change produces one removed +
one added row, NOT a "modified" entry. This is by design (per
REQ-LIN-F5-002 spec) and the response shape always carries
`modified: []`.

## How to use

1. Open a contract → **Lineage** tab.
2. Pick a date with the "As of" picker OR a version with the
   dropdown.
3. Click "Apply".
4. (Optional) Tick "Show diff vs. live" to see the diff between
   the anchor and now.

## Notes

- Cross-region access requires the `X-Lineage-Cross-Region-Consent: true`
  header when your tenant has `data_residency_region` set.
- Both anchors at once → HTTP 400 (mutually exclusive per spec).
- Capability flag OFF → params silently ignored, current state
  returned.

## Related

- [Time-travel runbook](../runbooks/lineage-snapshots-dod-evidence.md)
- [Archive policy (OP-3)](../architecture/lineage-archive-op3.md)
- [Capacity script](../../scripts/lineage_history_growth.py)
- [Support FAQ](../support/lineage-faq.md)
