# STRIDE Threat Model — Event Bus & Integrity (W4)

One-pager for the oss-release-remediation W4 surface (event-bus
dedup/publishing, search reindex, locked contract versions). Every
mitigation cites its verifying test or gate (P4). Ledger:
`docs/audits/w111-threat-model-refresh-2026-10-15.md`.

## Scope / assets

- The event bus (publish, dedup keys, on_commit delivery, the
  listener), event emitters (contract lifecycle, marketplace
  notifications), the search-index reindex path, and the contract
  version allocation under concurrency.

## Trust boundaries

- Application services → event bus → subscribers (in-process + the
  worker listener).
- Application → Redis (dedup namespaces).
- Application → PostgreSQL (events, SearchIndex rows, contract
  versions).

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Self-published events suppressed as "already processed" | Publisher keys `event:sent:*` and per-subscriber consumer keys `event:cons:<subscriber>:*` are SEPARATE namespaces (the shared-namespace self-dedup root cause closed) | `hub/apps/core/events/tests/test_w41_event_bus_contract.py` |
| Phantom events after rollback | `EventBus.publish` defers delivery to `transaction.on_commit` inside atomics — a rollback produces no event and no dedup key | `hub/apps/core/events/tests/test_w41_event_bus_contract.py` |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Contract version allocation race (read-max-then-insert) | The 8 unlocked sites route through `locked_contract_version()`; residual IntegrityError → 409 `CONTRACT_VERSION_CONFLICT` | `hub/apps/contracts/tests/test_w44_version_allocation.py` |
| Event dedup key collision across events | Atomic `check_and_store_event` (SET NX EX) — one claim per key | `hub/apps/core/events/tests/test_w41_event_bus_contract.py` |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Emitter decisions undocumented | Decision table committed (`contract.created` EMITTED, marketplace publisher WIRED, `contract.validated` ABSENT pinned, etc.) | `docs/audits/event-emitter-decisions-2026-10-09.md` |
| Dead emitters pass silently | Emitter presence/absence pinned per decision (C1–C7) | `hub/apps/core/events/tests/test_w41b_event_emitters.py` |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| SearchIndex rows stale or cross-tenant | `reindex_contract` rebuilds the full row; the ImportError swallow in the trigger path removed (failures visible) | `hub/apps/search/tests/test_w42_search_reindex.py` |
| Event payload leakage across tenants | Subscriber consumption state is per-subscriber namespaced — subscriber A's state never suppresses B's delivery | `hub/apps/core/events/tests/test_consumer_deduplication.py` |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Events never delivered (bus never listened) | `EventBusListener` starts one worker thread per subscriber (`EVENT_BUS_LISTENER_ENABLED` deployed true in staging + helm) | `hub/apps/core/events/tests/test_w41_event_bus_contract.py` |
| Reindex storms on every write | Reindex enqueued on the low-priority queue via the delegator, not inline | `hub/apps/search/tests/test_w42_search_reindex.py` |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Marketplace notifications fire without entitlements | `MarketplaceEventPublisher` wired through the bus (was structurally dead — now emits) with tenant attribution | `hub/apps/core/events/tests/test_w41b_event_emitters.py` |
| Contract version bypass via the ml surface | Conflict translation applied there too (no misleading 400 re-wrap) | `hub/apps/contracts/tests/test_w44_version_allocation.py` |

## Open threats (not yet shipped — documented, not claimed)

- Cross-service delivery durability (Kafka-style persistence) is
  out of scope for the OSS core — the bus is in-process/Redis-backed
  with the worker listener as the deployed delivery path.
- The falsifiability harness covers the new gates; event-bus-specific
  DAST remains a W11 lane.
