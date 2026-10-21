# Lineage F4 — OpenLineage integration

**Audience:** Data engineers operating Airflow / dbt / custom producers
**Capability flag:** `lineage.openlineage_export`

## What it does

Bidirectional bridge between Meshant's contract-centric lineage and
the OpenLineage 2.0.0 standard:

- **Outbound** — every contract save fans a translated `RunEvent`
  to your Marquez (or other OpenLineage receiver).
- **Inbound** — your producers (Airflow, dbt) POST `RunEvents` to
  Meshant; we translate into the `LineageEdge` index.

Quick-start, key management, HMAC signing, and DLQ replay are
documented in detail at:

- [docs/integrations/openlineage.md](../integrations/openlineage.md) — integration guide
- [docs/integrations/openlineage-infra.md](../integrations/openlineage-infra.md) — infrastructure
- [docs/runbooks/openlineage-dlq-replay.md](../runbooks/openlineage-dlq-replay.md) — DLQ runbook
- [docs/runbooks/marquez-outage.md](../runbooks/marquez-outage.md) — outage runbook
- [docs/runbooks/marquez-upgrade.md](../runbooks/marquez-upgrade.md) — upgrade runbook

## Quick links

- Get an ingest key: `/admin/integrations/openlineage` → "Generate key".
- Rotate keys (operator): `python manage.py rotate_openlineage_keys --tenant=<id>`.
- Replay the DLQ: `python manage.py replay_openlineage_dlq --max=500`.

## Related

- [Support FAQ](../support/lineage-faq.md)
- [SECURITY.md](../../SECURITY.md) — bug-bounty scope.
