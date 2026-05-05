"""
Phase 240.1.A.7 — canonical audit-event action constants.

Every audit row created from production code SHOULD reference one of
these constants instead of inlining a string literal — that way the
linter / type-checker catches a typo at the import site rather than
at audit-replay time when the row is already persisted.

Constants follow a "name == value" convention so that audit rows are
self-describing without an out-of-band lookup table:

    >>> from hub.apps.audit import event_types
    >>> event_types.DQ_ALERT_DELIVERED
    'DQ_ALERT_DELIVERED'

This module intentionally has zero runtime imports beyond ``__future__``
so it can be loaded in any context (signal handler, migration, RQ task)
without dragging in Django app-config side-effects.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Resource-type constants
# ---------------------------------------------------------------------------

#: ``resource_type`` value used on every DQ-alert audit row.
#: Pin once so audit-replay queries never need to UNION across drift.
DQ_ALERT_RESOURCE_TYPE: str = "DQ_ALERTING_RULE"

#: Phase 250.1.A.7 — ``resource_type`` value used on every asset-related
#: audit row. The asset-creation workflow, the data-first endpoint and
#: the saga-rollback path all emit rows under this single string so
#: audit-replay queries scoped to ``resource_type='ASSET'`` see every
#: lifecycle event without having to UNION across drift.
ASSET_RESOURCE_TYPE: str = "ASSET"


# ---------------------------------------------------------------------------
# DQ alerting pipeline (Phase 240.1.A)
# ---------------------------------------------------------------------------

#: Successful delivery to a configured channel.
#: ``details_json`` carries: channel, delivery_id, alert_id, rule_id, run_id.
DQ_ALERT_DELIVERED: str = "DQ_ALERT_DELIVERED"

#: Delivery attempt failed (will be retried unless retry budget exhausted).
#: ``details_json`` carries: channel, alert_id, rule_id, error, attempt_number.
DQ_ALERT_FAILED: str = "DQ_ALERT_FAILED"

#: Retry budget exhausted — alert moved to dead-letter queue.
#: ``details_json`` carries: channel, alert_id, rule_id, last_error,
#: total_attempts, dead_lettered_at.
#: This event also pages the ops PagerDuty (NOT the customer-facing one)
#: per D240.8.
DQ_ALERT_DEAD_LETTER: str = "DQ_ALERT_DEAD_LETTER"

#: Per-channel circuit breaker tripped to OPEN. Subsequent deliveries
#: short-circuit until the breaker recovers.
#: ``details_json`` carries: channel, tenant_id, failure_count,
#: timeout_seconds, circuit_breaker_name.
DQ_ALERT_CHANNEL_DEGRADED: str = "DQ_ALERT_CHANNEL_DEGRADED"


# ---------------------------------------------------------------------------
# Fail-closed-at-intake asset-creation events (Phase 250.1.A.7)
# ---------------------------------------------------------------------------

#: Compliance OR DQ pre-persistence gate returned FAIL and the
#: asset-creation workflow refused to persist the Asset row. The audit
#: row is the only durable record of the rejected intake (no Asset row
#: exists), so it must carry enough context for incident-response and
#: tenant support to reconstruct what was attempted.
#:
#: ``details_json`` carries: tenant_id, file_id (nullable), key, name,
#: gate (``"compliance"`` | ``"dq"``), gate_status (``"FAIL"`` |
#: ``"UNKNOWN"``), gate_reason, compliance_run_id (nullable),
#: dq_run_id (nullable), workflow_instance_id, correlation_id.
ASSET_FAIL_CLOSED_REJECTED: str = "ASSET_FAIL_CLOSED_REJECTED"

#: A downstream asset-creation step failed AFTER the Asset row was
#: persisted; the saga compensation map ran and the workflow rolled
#: back the partial chain (dataset/contract attachments, ODPS link,
#: search-index entries) and either deleted the Asset row or left it
#: in DRAFT depending on which step failed and the configured
#: compensation policy.
#:
#: ``details_json`` carries: tenant_id, asset_id, workflow_instance_id,
#: failed_step, compensation_steps (list of step names that were
#: undone), final_asset_status, correlation_id.
ASSET_WORKFLOW_ROLLED_BACK: str = "ASSET_WORKFLOW_ROLLED_BACK"

#: Phase 250.1.E.1 — emitted by the daily orphan-DRAFT cleanup sweep
#: (``hub/apps/assets/management/commands/cleanup_orphan_drafts.py``)
#: for every batch of orphan ``Asset`` rows hard-deleted (or counted in
#: dry-run mode). Orphan = ``status=DRAFT`` AND age > 30 days; these
#: are the long-tail of pre-Phase-250.1.A workflow runs that never
#: progressed past ``DRAFT``, plus any future runs that abort between
#: ``asset_create`` and ``activate`` without compensation deletion.
#:
#: ``details_json`` carries: tenant_id, count, dry_run, batch (1-indexed
#: batch number within the tenant), age_threshold_days, asset_ids
#: (sample — first 10 ids of the batch for triage), correlation_id.
ASSET_ORPHAN_DRAFT_PURGED: str = "ASSET_ORPHAN_DRAFT_PURGED"

#: Phase 250.2.A.3 (closes Gap 2) — emitted by the asset-creation
#: workflow's ``_activate_asset_task`` when an asset transitions
#: from ``DRAFT`` to ``ACTIVE`` automatically because all upstream
#: gates (DQ, compliance, contract validation, structural floor)
#: passed AND the resolved effective auto-activate flag was True.
#: Distinguishes auto-activation (gate-driven) from manual
#: activation (caller-explicit save of an existing DRAFT) — the
#: lifecycle-summary ``ASSET_ACTIVATED`` event still fires in
#: ``_audit_logging_task`` regardless of activation source.
#:
#: ``details_json`` carries: tenant_id, asset_id, workflow_instance_id,
#: previous_status (DRAFT), new_status (ACTIVE), dq_status (at
#: activation time), compliance_status (at activation time),
#: caller_auto_activate (the per-call value the API caller passed
#: to ``execute()``), tenant_auto_activate (the value of
#: ``Tenant.asset_auto_activate_on_gate_pass`` at execute time),
#: resolved_auto_activate (the AND of the two — always True for
#: this event since it only fires on activation).
ASSET_AUTO_ACTIVATED: str = "ASSET_AUTO_ACTIVATED"

#: Phase 250.2.B.4 (closes Gap 3) — emitted by the asset-creation
#: workflow's ``_compare_schema_against_contract_task`` whenever the
#: deterministic schema-diff between the contract's declared
#: ``hub_contract_json["schema"]`` and the dataset's
#: inference-time schema produces ANY drift (severity ≥ WARN).
#:
#: This event fires on BOTH the WARN tier (extra fields only OR
#: compatible widenings) and the FAIL tier (missing fields OR
#: incompatible type mismatches). The severity field in the
#: payload disambiguates so audit-replay queries can filter on
#: only the fail-blocking subset if needed.
#:
#: ``details_json`` carries: tenant_id, asset_id, contract_id,
#: dataset_id, workflow_instance_id, severity (``WARN`` /
#: ``FAIL``), missing_fields (list — REDACTED to first 20 names
#: per the audit-payload size cap from Phase 240.5.F),
#: extra_fields (same redaction), type_mismatches (list of
#: ``{field, contract_type, dataset_type, compatible}`` dicts —
#: same redaction), structural_incompatibility (bool).
ASSET_SCHEMA_DRIFT_DETECTED: str = "ASSET_SCHEMA_DRIFT_DETECTED"

#: Phase 250.3.B.3 — fired by the Asset model's ``visibility`` setter
#: (and by the views/serializers/services that absorb the legacy
#: ``visibility=`` kwarg) whenever a phase-1-deprecation-window write
#: is attempted. Drives the deprecation telemetry that gates the
#: phase-2 column-drop per D250.4: phase-2 only ships after three full
#: release cycles of zero ``ASSET_VISIBILITY_WRITE_DEPRECATED`` events.
#:
#: ``details_json`` carries: ``tenant_id`` (str | None), ``asset_id``
#: (str | None — None for pre-save writes), ``attempted_value`` (the
#: legacy value the caller tried to set, e.g. ``"PUBLIC"`` /
#: ``"INTERNAL"``), ``call_site`` (best-effort string identifying the
#: caller surface — ``"model.setter"`` / ``"serializer"`` / ``"view"``
#: / ``"service"``), ``current_status`` (the asset's ``status`` field
#: which now drives the derived visibility), ``derived_visibility``
#: (the value the property would return after the no-op).
#:
#: ``result`` is always ``"WARNING"`` — the write is silently ignored
#: but it's a non-success outcome from the caller's perspective.
ASSET_VISIBILITY_WRITE_DEPRECATED: str = "ASSET_VISIBILITY_WRITE_DEPRECATED"

#: Phase 250.5.A.3 — fired when ``DiscoveryService.create_federated_asset_with_contracts``
#: refuses to import because (a) the consumer tenant's
#: ``federated_import_enabled`` flag is False (per D250.3 default),
#: OR (b) the cross-region consent gate (250.5.A.6) blocks the call,
#: OR (c) the source / connection is otherwise ineligible.
#:
#: ``details_json`` carries: ``code`` (one of
#: ``"FEDERATED_IMPORT_DISABLED"`` / ``"CROSS_REGION_CONSENT_REQUIRED"``
#: / ``"COMPLIANCE_FAILED"``), ``tenant_id`` (consumer), ``connection_id``,
#: ``source_marketplace_type``, ``asset_key``, ``data_strategy`` and
#: any rejection-specific keys (e.g. ``source_region`` / ``consumer_region``
#: for the cross-region case).
#:
#: ``result`` is always ``"FAILURE"`` — the import was actively
#: refused (vs. ``WARNING`` for the deprecation surface).
FEDERATED_IMPORT_REJECTED: str = "FEDERATED_IMPORT_REJECTED"

#: Phase 250.5.A.6 / I2-3 — sub-class of the broader
#: ``FEDERATED_IMPORT_REJECTED`` event, dedicated to the cross-region
#: refusal so cross-region imports show up on dedicated dashboards
#: even if the broader rejection rate is high. Fires from the same
#: gate when ``consumer_tenant.data_residency_region !=
#: source_tenant.data_residency_region`` AND the call did NOT carry
#: ``cross_region_consent=True``.
#:
#: ``details_json`` carries: ``consumer_tenant_id``, ``source_tenant_id``,
#: ``consumer_region``, ``source_region``, ``connection_id``,
#: ``asset_key``. ``result`` is always ``"FAILURE"``.
FEDERATED_IMPORT_CROSS_REGION_BLOCKED: str = "FEDERATED_IMPORT_CROSS_REGION_BLOCKED"

#: Phase 250.5.A.5 / D250.16 — fired by the Tenant soft-delete signal
#: for each consumer-side ``ExternalResourceReference`` row whose
#: ``source_tenant_id`` matches the deleted tenant. The audit captures
#: the cascade event so the consumer tenant's ops have a durable
#: signal that an external-source has gone away (and the 90-day grace
#: countdown has started).
#:
#: ``details_json`` carries: ``source_tenant_id``, ``consumer_tenant_id``,
#: ``external_resource_reference_id``, ``asset_id``,
#: ``source_tenant_deleted_at`` (ISO-8601),
#: ``grace_window_expires_at`` (ISO-8601, source_tenant_deleted_at +
#: 90 days). ``result`` is always ``"WARNING"`` — the consumer-side
#: row is still queryable; it's a notice, not a failure.
FEDERATED_SOURCE_TENANT_DELETED: str = "FEDERATED_SOURCE_TENANT_DELETED"

#: Phase 250.6.D.1 (closes G2-1 / P2-1) — fired exactly ONCE per
#: tenant when ``Tenant.onboarding_completed_at`` transitions from
#: NULL to a timestamp. The transition happens when all three
#: onboarding signals first satisfy: a TENANT_ADMIN role grant,
#: ``kyc_status`` change away from UNVERIFIED, and an active
#: Subscription. The signal handler that observes the third signal
#: arriving (whichever it is — order-independent) calls
#: ``mark_onboarding_complete_if_ready`` which atomically sets the
#: timestamp + flips ``asset_creation_enabled`` to True; only on the
#: false→true return does the handler emit this event.
#:
#: ``details_json`` carries: ``tenant_id``, ``onboarding_completed_at``
#: (ISO-8601), ``triggered_by`` (one of ``"tenant_admin_assigned"`` /
#: ``"kyc_submitted"`` / ``"subscription_activated"`` — identifies
#: WHICH of the three signals was the LAST to arrive), and
#: ``asset_creation_enabled_after`` (always True — the flag
#: post-transition; included so audit consumers don't need to join
#: against the Tenant table).
#:
#: ``result`` is always ``"SUCCESS"`` — completion is never a
#: failure event. (A FAILURE shape would only make sense for a
#: "tried to mark complete but DB write failed" case, and that's
#: handled by the surrounding transaction's normal error path.)
ONBOARDING_COMPLETED: str = "ONBOARDING_COMPLETED"

#: Phase 250.6.E.1 — fired by the tenant feature-flags admin endpoint
#: at ``PATCH /api/v1/tenants/me/feature-flags/`` whenever a
#: TENANT_ADMIN flips a per-tenant capability flag (e.g.
#: ``federated_import_enabled``, ``asset_creation_enabled``,
#: ``asset_auto_activate_on_gate_pass``). The audit row is the
#: durable record of "who changed what when" — the SPA's settings
#: page reads these rows via the companion
#: ``GET /me/feature-flag-history/`` endpoint to render the audit-
#: log panel below the flag form.
#:
#: ``details_json`` carries: ``flag_name`` (string), ``previous_value``
#: (bool), ``new_value`` (bool), ``actor_user_id`` (UUID — set
#: redundantly to the audit row's actor_user_id FK so warehouse
#: queries on details_json don't need a JOIN), ``tenant_id`` (UUID).
#:
#: ``result`` is always ``"SUCCESS"`` — a failed PATCH (validation
#: error / unknown flag) returns 400 BEFORE the audit emission would
#: have fired, so this event only ever records successful changes.
TENANT_FEATURE_FLAG_UPDATED: str = "TENANT_FEATURE_FLAG_UPDATED"

#: Phase 250.7.A.2 (closes Gap 15) — emitted by the asset-creation
#: workflow's ``_index_for_search_task`` AND the
#: ``_activate_asset_task``'s semantic-mapping wrapper whenever a
#: post-activation best-effort step (search indexing via
#: ``SearchIndexer.index_asset`` OR semantic mapping via
#: ``map_asset_to_semantic``) fails. Per D250.6, these failures are
#: observability events, NOT gates: the asset still ACTIVATES on
#: degradation and ``Asset.semantic_status`` is flipped to ``"FAIL"``
#: so the SPA can render an inline "active but not yet discoverable"
#: banner with a retry CTA.
#:
#: ``details_json`` carries: ``tenant_id``, ``asset_id``,
#: ``workflow_instance_id``, ``degraded_step`` (one of
#: ``"index_for_search"`` / ``"activate_asset_semantic_map"`` —
#: distinguishes WHICH best-effort step failed so audit-replay
#: queries can isolate "search infra outage" from "Fuseki outage"),
#: ``error`` (str(exception)), ``previous_semantic_status``,
#: ``new_semantic_status`` (always ``"FAIL"`` for this event).
#:
#: ``result`` is always ``"WARNING"`` — a successful activation
#: that degraded ONE downstream surface is not a workflow failure
#: (the workflow completed; the post-activation indexing was
#: best-effort).
ASSET_SEMANTIC_DEGRADED: str = "ASSET_SEMANTIC_DEGRADED"

#: Phase 250.7.E.1 (closes Gap 17) — emitted by the asset-creation
#: workflow when non-fatal workflow warnings are recorded in
#: ``state_data.result_summary.warnings``. This gives audit-replay
#: visibility into degraded-but-successful runs without parsing logs.
#:
#: ``details_json`` carries: ``tenant_id``, ``asset_id``,
#: ``workflow_instance_id``, and ``result_summary`` where
#: ``result_summary.warnings`` is the exact warning payload surfaced to
#: API callers.
#:
#: ``result`` is always ``"WARNING"``.
ASSET_WORKFLOW_WARN_LOGGED: str = "ASSET_WORKFLOW_WARN_LOGGED"

#: Phase 260.A.5 — emitted whenever a request is denied because it
#: attempts to target a tenant different from the authenticated/request
#: tenant context.
CROSS_TENANT_DENIED: str = "CROSS_TENANT_DENIED"


__all__ = [
    "DQ_ALERT_RESOURCE_TYPE",
    "ASSET_RESOURCE_TYPE",
    "DQ_ALERT_DELIVERED",
    "DQ_ALERT_FAILED",
    "DQ_ALERT_DEAD_LETTER",
    "DQ_ALERT_CHANNEL_DEGRADED",
    "ASSET_FAIL_CLOSED_REJECTED",
    "ASSET_WORKFLOW_ROLLED_BACK",
    "ASSET_ORPHAN_DRAFT_PURGED",
    "ASSET_AUTO_ACTIVATED",
    "ASSET_SCHEMA_DRIFT_DETECTED",
    "ASSET_VISIBILITY_WRITE_DEPRECATED",
    "FEDERATED_IMPORT_REJECTED",
    "FEDERATED_IMPORT_CROSS_REGION_BLOCKED",
    "FEDERATED_SOURCE_TENANT_DELETED",
    "ONBOARDING_COMPLETED",
    "TENANT_FEATURE_FLAG_UPDATED",
    "ASSET_SEMANTIC_DEGRADED",
    "ASSET_WORKFLOW_WARN_LOGGED",
    "CROSS_TENANT_DENIED",
]
