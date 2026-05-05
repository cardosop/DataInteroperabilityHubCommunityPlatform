# B2-6 audit — Asset workflow webhook timing impact

**Audit task**: 250.0.11
**Audit date**: 2026-05-03
**Auditor**: Phase 250.0 Asset-Creation-Hardening pre-flight
**Status**: ✅ **CATALOGUED — 3 webhook emission points; timing-impact analysis below**

## Original gap statement

B2-6: "the workflow re-sequence in Phase 250.1.A flips Asset persistence from BEFORE-gates to AFTER-gates. This changes WHEN webhooks fire — and integrators may have built-in expectations about timing."

## Webhook emission inventory

The Hub has three asset-lifecycle webhook event publishers in [hub/apps/core/events/service_publishers.py](../../hub/apps/core/events/service_publishers.py):

| Publisher | Line | Webhook event type | Trigger today (pre-Phase-250) | Trigger after 250.1.A |
|---|---|---|---|---|
| `publish_asset_created` | 146 | `asset.created` | Fires immediately when `Asset.objects.create()` succeeds (BEFORE compliance + DQ gates run). Subscribers receive an event for an asset that may subsequently be rejected by gates. | Fires AFTER all gates pass and Asset row is materialised. Timing shifts from ~50 ms after API call → up to ~30 s after API call (gates run synchronously in-memory per D250.1). |
| `publish_asset_updated` | 168 | `asset.updated` | Fires on PATCH operations after row save. | Unchanged. |
| `publish_asset_activated` | 188 | `asset.activated` | Fires after the `activate` workflow step completes. Pre-Phase-250: Asset already exists when `activate` runs; webhook subscribers receive `asset.activated` after they've already received `asset.created`. | After 250.1.A, `auto_activate=True` is the default (D250.2), so `asset.created` and `asset.activated` MAY fire in the same workflow run — timing race for subscribers receiving both. |

Two additional integrations-side emission points fire on federated-import path:

- [hub/apps/integrations/services/discovery_service.py:710](../../hub/apps/integrations/services/discovery_service.py#L710) — federated-import workflow result includes `asset_activated` flag in audit/payload.
- [hub/apps/integrations/_services_legacy.py:3199](../../hub/apps/integrations/_services_legacy.py#L3199) — legacy mirror of above; B2-13 audit recommends consolidation.

## Timing-impact matrix (P1 risk)

For each webhook subscriber category, what is the impact of the 250.1.A re-sequence on their integration?

| Subscriber category | Pre-Phase-250 timing | Post-Phase-250 timing | Impact | Mitigation |
|---|---|---|---|---|
| **Synchronous downstream** (subscriber acts immediately on `asset.created`, e.g. provisions a workflow trigger) | ~50 ms after caller's POST | ~5–30 s after caller's POST (gates run) | **MEDIUM** — subscriber may time out their provisioning if relying on the prior 50 ms latency budget. | Document expected timing in `docs/mvpdocs/api-reference/webhooks.md` event payload section; bump expected-latency SLO in subscriber-facing docs. |
| **Async downstream** (subscriber queues the event for later processing) | ~50 ms | ~5–30 s | **LOW** — async subscribers typically don't care about webhook latency. | None needed; document the change in CHANGELOG. |
| **Auditor / observability** (subscriber records the event for compliance / lineage) | Both `asset.created` and gate-failure events received | NO `asset.created` event fires when gates fail — instead `ASSET_FAIL_CLOSED_REJECTED` audit event fires (NEW per 250.1.A). | **HIGH** — auditors expecting a gate-failure-tied-to-asset.created event will see a behaviour change. | Document explicitly: "with fail-closed enabled, `asset.created` fires only after gates pass; failures emit `ASSET_FAIL_CLOSED_REJECTED` audit event with the rejection reason." Add to webhook-payload reference docs. |
| **Frontend** (subscriber is the Hub's own React app, polling for asset status) | Polls workflow run; sees Asset row appear after gates | Same — but `state=COMPLETED` field on `WorkflowRun` becomes the canonical signal | **LOW** — frontend already polls workflow state per Phase 250.4 SDK pattern. | No change needed; ensures frontend consumes `WorkflowRun.state` not asset existence. |
| **External integrators** (third-party SaaS subscribed via webhook) | ~50 ms after caller's POST | ~5–30 s; potential `asset.created` non-emission on gate failure | **MEDIUM-HIGH** — third parties may be stuck on the prior contract. | Pre-merge announcement (250.0.18 protocol); 30-day deprecation window via `tenant.compliance_fail_closed_enabled` default-FALSE on existing tenants per D250.12. Subscribers MUST opt in. |

## Idempotency invariant

Webhook events MUST remain idempotent across the re-sequence. The Phase 233 webhook hardening idempotency check (`payload.event_id` deduplication in `service.py:223-238`) MUST remain effective — `asset.created` for the same asset MUST NEVER fire twice even if the workflow retries.

**Verification step** (to land in 250.1.G test plan): integration test that reproduces a workflow retry mid-flight + asserts `asset.created` webhook fires exactly once.

## Recommended remediation (250.1.G enhancement)

Phase 250 tasks.md sub-task **250.1.G** ("Webhook + internal-API consumer migration (MEDIUM, closes B2-6 / B2-7)") covers the migration. This audit adds:

1. **Wave 1 — pre-merge documentation**: update [docs/mvpdocs/api-reference/webhooks.md](../mvpdocs/api-reference/webhooks.md) `asset.created` event entry with the new latency expectations + the `ASSET_FAIL_CLOSED_REJECTED` audit event link.
2. **Wave 2 — internal eng announcement** (per 250.0.18 protocol): post in `#integrations-eng` 1 week before P1 deploy; office-hour Q&A; explicit list of affected webhook subscribers from the tenant DB.
3. **Wave 3 — soak per D250.12**: `tenant.compliance_fail_closed_enabled` default-FALSE on existing tenants for 30 days; default-TRUE on new tenants. Existing tenants opt-in via tenant-admin UI.
4. **Wave 4 — flip default** to TRUE on existing tenants after 14 d production-stable telemetry per D250.18 rollout discipline.

## Closeout

Phase 250 tasks.md sub-task 250.1.G references this audit report inline; the timing-impact matrix is the deliverable that integrators consume.
