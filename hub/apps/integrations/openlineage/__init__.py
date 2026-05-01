"""
Phase 228 F4 (228.F4.3) — OpenLineage standard integration.

Sub-package under ``hub.apps.integrations`` so the existing
``IntegrationsConfig.ready()`` lifecycle hook handles signal /
subscriber wiring without a new Django app entry. Models are
auto-discovered by Django's app loader because they live under a
recognised installed app's package tree.

Public surface
--------------

* :mod:`.translator` — bidirectional schema mapping between Meshant's
  internal lineage events and OpenLineage 2.0.0 ``RunEvent`` facets,
  with ``jsonschema`` validation against the upstream spec.
* :mod:`.adapter` — outbound emitter for the translated events:
  exponential backoff (1s → 16s, max 5 retries), DLQ on permanent
  failure, integrates with the existing ``django_rq`` queue.
* :mod:`.models` — :class:`OpenLineageIngestApiKey` (per-tenant ingest
  keys, bcrypt'd hash), :class:`OpenLineageDeadLetter` (encrypted
  payload archive of permanently-failed events).
* :mod:`.views` — REST endpoints: ``POST /lineage/openlineage/events/``
  (HMAC-signed inbound) and admin-only key management.
"""
