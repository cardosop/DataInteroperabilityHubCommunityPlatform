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

#: Phase 235.3 — emitted by the PLATFORM_ADMIN tenant-soft-delete
#: endpoint (``DELETE /api/v1/admin/tenants/{id}/``). The endpoint
#: stamps ``Tenant.scheduled_for_deletion_at = now()`` (alongside the
#: existing Phase 226 ``deleted_at`` field) and flips the tenant's
#: status to ``DELETED`` — the row stays in the database for a
#: 90-day grace window before the daily ``tenant_hard_delete_sweep``
#: cron hard-deletes it. ``details_json`` carries ``slug``,
#: ``display_name``, ``scheduled_for_deletion_at`` (ISO-8601), and
#: ``deleted_by`` (the PLATFORM_ADMIN's UUID — duplicated into
#: details so audit-replay surfaces it without joining
#: ``actor_user``). ``result`` is always ``"SUCCESS"`` — the
#: legal-hold + DSAR-restriction blockers return HTTP 422 BEFORE
#: this event would have fired.
TENANT_SOFT_DELETED: str = "TENANT_SOFT_DELETED"

#: Phase 235.3 — emitted by the daily ``tenant_hard_delete_sweep``
#: cron job IMMEDIATELY BEFORE the Tenant row is hard-deleted. The
#: audit row survives the cascade via the ``AuditEvent.tenant``
#: ``on_delete=SET_NULL`` contract (the tenant_id column nulls out
#: but the row stays — system-level audit history).
#:
#: Distinct from ``TENANT_HARD_DELETE_CASCADE`` (Phase 260.1.F) which
#: fires PER child row (one event per File) as the cascade walks
#: the FK graph — ``TENANT_HARD_DELETED`` is the ONE summary event
#: marking "the tenant itself was hard-deleted at this moment".
#:
#: ``details_json`` carries ``tenant_id`` (the deleted tenant's UUID
#: — recorded in details since the tenant FK is about to NULL),
#: ``slug``, ``display_name``, ``scheduled_for_deletion_at``
#: (ISO-8601 — proves the 90-day grace window had elapsed),
#: ``hard_deleted_at`` (ISO-8601), ``sweep_run_id`` (the cron
#: invocation's Job row id — links to the sweep summary).
#: ``actor_user`` is NULL (the cron is system-driven; the
#: PLATFORM_ADMIN's UUID lives on the matching
#: ``TENANT_SOFT_DELETED`` event 90+ days earlier — joinable via
#: ``details_json.tenant_id``).
TENANT_HARD_DELETED: str = "TENANT_HARD_DELETED"

#: Phase 235.4 — emitted by ``POST /api/v1/admin/impersonate/`` on a
#: successful start. ONE row is written per tenant context: one under
#: the impersonated user's tenant (the auditor-facing record) AND one
#: under the impersonator's home tenant (the security-team record).
#: Both rows carry the same ``impersonation_session_id`` in
#: ``details_json`` so audit-replay can correlate the two views.
#:
#: ``details_json`` carries: ``impersonation_session_id``,
#: ``impersonator_user_id``, ``impersonated_user_id``,
#: ``impersonator_tenant_id``, ``impersonated_tenant_id``,
#: ``max_minutes``, ``expires_at`` (ISO-8601), ``reason`` (operator
#: justification). ``result`` is always ``"SUCCESS"`` — rejection
#: paths (``IMPERSONATION_NOT_ENABLED``, ``TARGET_IS_PLATFORM_ADMIN``,
#: ``TARGET_INACTIVE``) emit ``IMPERSONATION_REJECTED`` instead.
IMPERSONATION_STARTED: str = "IMPERSONATION_STARTED"

#: Phase 235.4 — emitted when an impersonation session transitions
#: from ACTIVE to ENDED. Sources:
#:
#: * ``POST /api/v1/admin/impersonate/exit/`` (operator-driven) —
#:   ``end_reason="manual_exit"``.
#: * ``expire_impersonation_sessions`` cron (system-driven) —
#:   ``end_reason="expired"``.
#:
#: Emitted under the impersonated user's tenant context (the auditor-
#: facing record). ``details_json`` carries:
#: ``impersonation_session_id``, ``impersonator_user_id``,
#: ``impersonated_user_id``, ``impersonator_tenant_id``,
#: ``impersonated_tenant_id``, ``end_reason``, ``ended_at`` (ISO-8601),
#: ``started_at`` (ISO-8601 — duration reconstructable client-side).
#: ``result`` is always ``"SUCCESS"``.
IMPERSONATION_ENDED: str = "IMPERSONATION_ENDED"

#: Phase 235.4 — emitted when ``POST /api/v1/admin/impersonate/``
#: refuses to open a session. Captures the rejection so an auditor
#: can see WHICH PLATFORM_ADMIN ATTEMPTED an impersonation that the
#: platform refused. Distinct from ``IMPERSONATION_STARTED`` so
#: dashboards can distinguish successful capability use from refused
#: capability use.
#:
#: ``details_json`` carries: ``code`` (one of
#: ``"IMPERSONATION_NOT_ENABLED"`` / ``"TARGET_IS_PLATFORM_ADMIN"`` /
#: ``"TARGET_INACTIVE"``), ``impersonator_user_id``,
#: ``impersonated_user_id``, ``impersonated_tenant_id``, ``reason``
#: (operator justification — preserved on rejection too so an audit
#: replay can see what the operator was trying to do).
#: ``result`` is always ``"FAILURE"``.
IMPERSONATION_REJECTED: str = "IMPERSONATION_REJECTED"

#: Phase 235.2 — fired by the PLATFORM_ADMIN tenant-create endpoint
#: (``POST /api/v1/admin/tenants/``). Distinct from existing
#: self-service onboarding paths which emit the same action string as
#: a free-text literal — Phase 235.2 promotes the string to a pinned
#: constant so every emit site can be grepped and the wire format
#: can evolve under one source of truth.
#:
#: ``details_json`` carries: ``slug`` (the tenant's URL identifier),
#: ``display_name``, ``jurisdiction`` (the operator-chosen regime that
#: lands in ``TenantConfig.default_compliance_regimes``),
#: ``admin_email`` (the invited TENANT_ADMIN's email — recorded for
#: ops correlation), ``admin_user_id`` (the freshly-created User's
#: UUID), ``created_by`` (the PLATFORM_ADMIN's UUID — duplicated
#: into details so audit-replay surfaces it without joining
#: ``actor_user``). ``result`` is always ``"SUCCESS"``.
#:
#: The actor_user on this row is the PLATFORM_ADMIN who issued the
#: create request (the writer), NOT the invited user.
TENANT_CREATED: str = "TENANT_CREATED"

#: Phase 235.1 — fired by the PLATFORM_ADMIN per-tenant feature-flag flip
#: endpoint (``PUT /api/v1/admin/tenants/{id}/feature-flags/``). Distinct
#: from ``TENANT_FEATURE_FLAG_UPDATED`` (Phase 250.6.E.1) which fires
#: from the TENANT_ADMIN self-service path — admin-flow audits carry an
#: ``approver`` field (same as ``requested_by`` for non-sensitive flags;
#: the second admin's UUID for sensitive flags that traversed the
#: two-person rule). ``details_json`` carries ``flag``, ``old_value``,
#: ``new_value``, ``reason`` (the operator's min-10-char justification),
#: ``requested_by`` (UUID), ``approver`` (UUID). ``result`` is always
#: ``"SUCCESS"`` — a rejected flip (validation / unknown flag / rate
#: limit) returns HTTP 4xx BEFORE the audit emission fires.
TENANT_FEATURE_FLAG_CHANGED: str = "TENANT_FEATURE_FLAG_CHANGED"

#: Phase 235.1 — fired when a PLATFORM_ADMIN requests a sensitive
#: flag flip (one tagged ``sensitive=True`` in
#: :mod:`hub.apps.tenants.feature_flag_registry`). The request creates
#: a ``FeatureFlagFlipApproval`` row in ``pending`` status; the flag
#: does NOT change until a SECOND PLATFORM_ADMIN approves.
#: ``details_json`` carries ``flag``, ``requested_value``, ``reason``,
#: ``requested_by``, ``approval_id``, ``tenant_id``. ``result`` is
#: always ``"SUCCESS"`` (the approval-row creation succeeded; the
#: pending flip itself isn't a success yet).
FEATURE_FLAG_FLIP_APPROVAL_REQUESTED: str = "FEATURE_FLAG_FLIP_APPROVAL_REQUESTED"

#: Phase 235.1 — fired when a SECOND PLATFORM_ADMIN approves a pending
#: ``FeatureFlagFlipApproval`` row, AT WHICH POINT the flag value
#: actually changes. ``details_json`` carries ``flag``,
#: ``requested_value``, ``reason``, ``requested_by``, ``approver``,
#: ``approval_id``, ``tenant_id``. The matching
#: ``TENANT_FEATURE_FLAG_CHANGED`` event fires in the same transaction
#: with the resolved ``approver`` field — both events are forensically
#: linked via ``approval_id`` so audit-replay can reconstruct the
#: full two-person-rule transition.
FEATURE_FLAG_FLIP_APPROVED: str = "FEATURE_FLAG_FLIP_APPROVED"

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

#: Phase 260.C.2 — emitted by the stale unverified-user cleanup command
#: when an old unverified user account is hard-deleted.
USER_DELETED_UNVERIFIED: str = "USER_DELETED_UNVERIFIED"

#: Phase 260.C.4 — emitted when ``UserTenantMembership`` is created (grant).
#: ``details_json`` carries: ``subject_user_id``, ``actor_user_id`` (nullable),
#: ``tenant_id``, ``membership_id``, ``reason``.
MEMBERSHIP_GRANTED: str = "MEMBERSHIP_GRANTED"

#: Phase 260.C.4 — emitted when ``UserTenantMembership`` is deleted (revoke).
#: ``details_json`` carries: ``subject_user_id``, ``actor_user_id`` (nullable),
#: ``tenant_id``, ``membership_id`` (the removed row's primary key),
#: ``reason``.
MEMBERSHIP_REVOKED: str = "MEMBERSHIP_REVOKED"

#: Phase 231.1 — compliance intake scan enqueued after Asset registration (gate on).
#: ``details_json`` carries: ``asset_id``, ``tenant_id``, ``compliance_run_id``, ``job_id``.
COMPLIANCE_INTAKE_SCAN_ENQUEUED: str = "COMPLIANCE_INTAKE_SCAN_ENQUEUED"

#: Phase 231.1 — asset activation blocked because intake gate is not satisfied.
COMPLIANCE_INTAKE_GATE_BLOCK: str = "COMPLIANCE_INTAKE_GATE_BLOCK"

#: Phase 231.2 — publish blocked by tenant compliance gate before publication rules.
#: Covers ``NO_SUCCEEDED_RUN`` and ``LEVEL_EXCEEDS_THRESHOLD`` cases; discriminate via
#: ``details.gate_code`` / ``details.reason`` (API may return ``COMPLIANCE_RUN_REQUIRED`` vs
#: ``COMPLIANCE_THRESHOLD_EXCEEDED``).
COMPLIANCE_THRESHOLD_EXCEEDED: str = "COMPLIANCE_THRESHOLD_EXCEEDED"

#: Phase 231.2 — ``TenantConfig.compliance_risk_threshold`` changed.
TENANT_COMPLIANCE_THRESHOLD_CHANGED: str = "TENANT_COMPLIANCE_THRESHOLD_CHANGED"

#: Phase 231.2 — PLATFORM_ADMIN published listing with ``force_publish=True``.
COMPLIANCE_GATE_OVERRIDDEN: str = "COMPLIANCE_GATE_OVERRIDDEN"

#: Phase 231.4 — scrubbed ``compliance.completed`` webhook dispatched for a terminal run.
COMPLIANCE_WEBHOOK_FIRED: str = "COMPLIANCE_WEBHOOK_FIRED"

#: Phase 233.1 — webhook signing key rotated via ``POST /webhooks/{id}/rotate_secret/``.
WEBHOOK_KEY_ROTATED: str = "WEBHOOK_KEY_ROTATED"

#: Phase 233.1 — retiring webhook signing key transitioned to retired by the hourly cron.
WEBHOOK_KEY_RETIRED: str = "WEBHOOK_KEY_RETIRED"

#: Phase 233.3 — outbound webhook delivery rate-limited per the tenant's
#: per-minute budget (REQ-WH-RL-004).
WEBHOOK_RATE_LIMIT_EXCEEDED: str = "WEBHOOK_RATE_LIMIT_EXCEEDED"

#: Phase 231.8 — user or API client exported compliance run data (CSV/JSON).
COMPLIANCE_EXPORT: str = "COMPLIANCE_EXPORT"

#: API-initiated compliance run row created (``ComplianceRunViewSet.create`` audit).
COMPLIANCE_RUN_CREATED: str = "COMPLIANCE_RUN_CREATED"

#: User cancelled an in-flight run (underlying job marked cancelled).
COMPLIANCE_RUN_CANCELLED: str = "COMPLIANCE_RUN_CANCELLED"

#: Actor fetched detailed results payload for a run (results wire / audit trail).
RESULTS_ACCESSED: str = "RESULTS_ACCESSED"

#: Compliance microservice circuit breaker is OPEN; asset ``compliance_status`` degraded to WARN.
COMPLIANCE_SERVICE_UNAVAILABLE: str = "COMPLIANCE_SERVICE_UNAVAILABLE"

#: Phase 232.1 — consent ledger (ConsentRecord / ConsentPurpose lifecycle).
CONSENT_GRANTED: str = "CONSENT_GRANTED"
CONSENT_REVOKED: str = "CONSENT_REVOKED"
CONSENT_PURPOSE_CHANGED: str = "CONSENT_PURPOSE_CHANGED"

#: Phase 232.4 — RoPA artefact materialised to object storage (register export).
ROPA_GENERATED: str = "ROPA_GENERATED"

#: Phase 232.3 — breach incident lifecycle.
BREACH_INCIDENT_OPENED: str = "BREACH_INCIDENT_OPENED"
BREACH_INCIDENT_STATUS_CHANGED: str = "BREACH_INCIDENT_STATUS_CHANGED"
BREACH_NOTIFICATION_SENT: str = "BREACH_NOTIFICATION_SENT"
BREACH_SLA_WARN_WINDOW: str = "BREACH_SLA_WARN_WINDOW"
BREACH_SLA_CRITICAL_WINDOW: str = "BREACH_SLA_CRITICAL_WINDOW"
BREACH_SLA_OVERDUE: str = "BREACH_SLA_OVERDUE"

#: Phase 232.6 — processor agreement tracker.
PROCESSOR_REGISTERED: str = "PROCESSOR_REGISTERED"
PROCESSOR_UPDATED: str = "PROCESSOR_UPDATED"
PROCESSOR_AGREEMENT_CREATED: str = "PROCESSOR_AGREEMENT_CREATED"
PROCESSOR_AGREEMENT_UPDATED: str = "PROCESSOR_AGREEMENT_UPDATED"
PROCESSOR_AGREEMENT_SUBPROCESSOR_CHANGED: str = "PROCESSOR_AGREEMENT_SUBPROCESSOR_CHANGED"
PROCESSOR_AGREEMENT_EXPIRY_WARN_60: str = "PROCESSOR_AGREEMENT_EXPIRY_WARN_60"
PROCESSOR_AGREEMENT_EXPIRY_WARN_30: str = "PROCESSOR_AGREEMENT_EXPIRY_WARN_30"
PROCESSOR_AGREEMENT_EXPIRY_WARN_7: str = "PROCESSOR_AGREEMENT_EXPIRY_WARN_7"
PROCESSOR_AGREEMENT_EXPIRED: str = "PROCESSOR_AGREEMENT_EXPIRED"
PROCESSOR_AGREEMENT_DELETED: str = "PROCESSOR_AGREEMENT_DELETED"
PROCESSOR_REMOVED: str = "PROCESSOR_REMOVED"

#: Phase 232.5 — DPIA register and review workflow.
DPIA_CREATED: str = "DPIA_CREATED"
DPIA_SUBMITTED: str = "DPIA_SUBMITTED"
DPIA_REVIEW_DECISION: str = "DPIA_REVIEW_DECISION"
DPIA_SUPERSEDED: str = "DPIA_SUPERSEDED"
DPIA_PERIODIC_REVIEW_OPENED: str = "DPIA_PERIODIC_REVIEW_OPENED"

#: Phase 232.7 — automated retention enforcement (tombstone + hard delete).
RETENTION_RESOURCE_TOMBSTONED: str = "RETENTION_RESOURCE_TOMBSTONED"
RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP: str = "RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP"
RETENTION_POLICY_LEGAL_HOLD_UPDATED: str = "RETENTION_POLICY_LEGAL_HOLD_UPDATED"
RETENTION_AUTOSWEEP_COMPLETED: str = "RETENTION_AUTOSWEEP_COMPLETED"

#: Phase 234.5 — TENANT_ADMIN created a per-event-type audit retention
#: override (``AuditEventRetentionPolicy``). ``details_json`` carries
#: ``policy_id``, ``event_type``, ``retention_days``, ``regulation_keys``,
#: ``enabled``. Emitted from the CRUD ViewSet under
#: ``/api/v1/audit/event-retention-policies/``.
AUDIT_EVENT_RETENTION_POLICY_CREATED: str = "AUDIT_EVENT_RETENTION_POLICY_CREATED"

#: Phase 234.5 — TENANT_ADMIN updated an existing override. ``details_json``
#: carries the same fields as CREATED plus the previous ``retention_days``
#: under ``previous_retention_days`` so audit-replay can reconstruct
#: history without an additional join.
AUDIT_EVENT_RETENTION_POLICY_UPDATED: str = "AUDIT_EVENT_RETENTION_POLICY_UPDATED"

#: Phase 234.5 — TENANT_ADMIN deleted an override. ``details_json``
#: carries ``policy_id``, ``event_type``, last ``retention_days`` (so the
#: row's effective state at deletion time is reconstructable).
AUDIT_EVENT_RETENTION_POLICY_DELETED: str = "AUDIT_EVENT_RETENTION_POLICY_DELETED"

#: Phase 234.7.1 — emitted by the chain-integrity verifier endpoint
#: (``GET /api/v1/audit/integrity/verify``) on a clean verification.
#: ``details_json`` carries ``checked`` (rows walked), ``gaps`` (count
#: of GDPR-erasure gaps reported as informational by the verifier —
#: present but NOT a tamper signal), ``include_snapshots`` (bool,
#: whether the Merkle cross-check ran), ``snapshots_checked``
#: (when applicable). ``result`` is always ``"SUCCESS"``.
#:
#: Pinned as the durable "we ran the verifier and the chain is
#: intact" beacon — an auditor reconstructing a regulatory-period
#: timeline from the audit log alone can see when the chain was last
#: machine-verified, not just rely on Grafana history.
AUDIT_INTEGRITY_VERIFIED: str = "AUDIT_INTEGRITY_VERIFIED"

#: Phase 234.7.1 — emitted by the chain-integrity verifier when the
#: verification FAILS (mismatches present OR snapshot cross-check
#: surfaces forged roots). ``details_json`` carries: ``checked``,
#: ``mismatch_count``, ``mismatches`` (sample of up to 10 — full list
#: queryable from the verifier response by re-running), ``gaps``
#: (count, informational), ``snapshot_mismatches`` (count when
#: applicable), ``tenant_id``. ``result`` is always ``"FAILURE"``.
#:
#: This is the load-bearing tamper-detected signal — alerting on
#: ``AUDIT_INTEGRITY_MISMATCH`` is the on-call PagerDuty path. The
#: row is itself an audit event so its own creation is part of the
#: chain; an attacker that can't both forge the original event AND
#: this meta-audit doesn't get to silence the alert.
AUDIT_INTEGRITY_MISMATCH: str = "AUDIT_INTEGRITY_MISMATCH"

#: Phase 234.7.1 — emitted on GDPR right-to-erasure completion when
#: an erasure-class DSAR removes audit-events that referenced the
#: subject. Distinct from ``AUDIT_RETENTION_PURGED`` (which is the
#: time-based retention sweep) — this fires on subject-driven,
#: regulator-mandated deletion regardless of retention age.
#:
#: ``details_json`` carries: ``dsar_request_id``, ``subject_user_id``
#: (NULL if the subject was un-linked), ``deleted_count``,
#: ``deleted_event_ids`` (sample capped at 100 like
#: ``AUDIT_RETENTION_PURGED``), ``tenant_id``, ``regulator_regime``
#: (e.g. ``"GDPR"`` / ``"UK_GDPR"`` / ``"LGPD"``), ``actor_user_id``
#: (the DPO who fulfilled the DSAR). ``result`` is always
#: ``"SUCCESS"`` — the DSAR machinery handles failure flows
#: separately.
#:
#: Per the GDPR contract: this row itself survives the erasure
#: because it carries no PII about the subject (only their
#: pseudonymous UUID), and audit history of the erasure ITSELF is a
#: separate retention scope — supervisory authorities expect proof
#: that the erasure happened.
AUDIT_GDPR_PURGED: str = "AUDIT_GDPR_PURGED"

#: Phase 234.4 — meta-audit emitted by the audit-permanent-delete sweep
#: BEFORE it hard-deletes archived AuditEvent rows past the 90-day grace
#: window. The row is the durable receipt that the deletion happened —
#: written as a live (non-archived) audit event so the sweep itself
#: cannot purge it. Distinct from
#: ``RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP`` (which deletes the
#: BUSINESS resource — asset/dataset/file — under a per-policy retention
#: window). This event deletes audit history, not business data, and
#: closes the GDPR right-to-erasure loop on the audit trail itself.
#:
#: One row is emitted per (tenant, run) — bulk sweeps must NOT flood the
#: audit log with one row per deleted event. ``details_json`` carries:
#: ``tenant_id`` (str | "__platform__"), ``deleted_count`` (int),
#: ``deleted_event_ids`` (list — truncated to the first 100 ids so the
#: payload stays bounded; ``deleted_count`` alone is the authoritative
#: deletion telemetry — IDs are forensic spot-checks), ``dry_run`` (bool),
#: ``age_threshold_days`` (int — the cutoff the sweep applied),
#: ``skipped_dsar_restriction`` (int — events kept because an open DSAR
#: RESTRICTION covered their resource).
#:
#: ``result`` is always ``"SUCCESS"`` — failures in the sweep are recorded
#: on the Job row, not as a per-tenant audit event.
AUDIT_RETENTION_PURGED: str = "AUDIT_RETENTION_PURGED"
#: Phase 277.B.013c — emitted when a user requests a GDPR data export
#: (Article 15 / Article 20 right of access + portability). Carries
#: ``user_id``, ``tenant_id``, ``job_id`` so the audit trail links
#: to the DataExportJob row.
#:
#: ``result`` is ``"SUCCESS"`` when the job was created; ``"FAILURE"``
#: when creation was rejected (duplicate/rate-limit).
DATA_EXPORT_CREATED: str = "DATA_EXPORT_CREATED"
#: Phase 277.B.013c — emitted when a GDPR data export job completes
#: (success or failure). Carries ``user_id``, ``tenant_id``,
#: ``job_id``, ``status`` (COMPLETED/FAILED), ``format_version``,
#: and ``storage_path`` on success. GDPR Article 15 proof-of-action.
#:
#: ``result`` is ``"SUCCESS"`` on COMPLETED, ``"FAILURE"`` on FAILED.
DATA_EXPORT_COMPLETED: str = "DATA_EXPORT_COMPLETED"
#: Phase 277.B.030 — emitted when a scheduled export is created.
#: Carries ``scheduled_export_id``, ``tenant_id``, ``user_id``.
SCHEDULED_EXPORT_CREATED: str = "SCHEDULED_EXPORT_CREATED"
#: Phase 277.B.030 — emitted when a scheduled export is updated.
#: Carries ``scheduled_export_id``, ``tenant_id``, ``user_id``,
#: ``changed_fields``.
SCHEDULED_EXPORT_UPDATED: str = "SCHEDULED_EXPORT_UPDATED"
#: Phase 277.B.030 — emitted when a scheduled export is deleted.
#: Carries ``scheduled_export_id``, ``tenant_id``, ``user_id``.
SCHEDULED_EXPORT_DELETED: str = "SCHEDULED_EXPORT_DELETED"
#: Phase 277.B.030 — emitted when a scheduled export is triggered
#: for immediate execution. Carries ``scheduled_export_id``,
#: ``tenant_id``, ``user_id``, ``run_id``.
SCHEDULED_EXPORT_TRIGGERED: str = "SCHEDULED_EXPORT_TRIGGERED"
#: Phase 277.B.032 — emitted when a PLATFORM_ADMIN inspects a
#: tenant's onboarding state via the admin endpoint. Carries
#: ``tenant_id`` and the full ``onboarding_state`` dict.
TENANT_ONBOARDING_STATE_VIEWED: str = "TENANT_ONBOARDING_STATE_VIEWED"
#: Phase 260.1.A — hard purge of a file after soft-delete grace.
#: ``details_json`` (PII-redacted): original ``name``, ``content_sha256``,
#: ``size``, ``tenant_id``, ``actor_user_id`` (system purge → NULL),
#: ``timestamp`` (ISO-8601), ``file_id``, ``dry_run``.
FILE_PURGED: str = "FILE_PURGED"
#: Phase 260.1.B — last Dataset reference removed under eligible asset lineage; file enters DELETED.
FILE_ORPHAN_DETECTED: str = "FILE_ORPHAN_DETECTED"
#: Phase 260.1.D — abandoned multipart (>24h) aborted; correlated File.UPLOADING → DELETED.
FILE_MULTIPART_ABANDONED: str = "FILE_MULTIPART_ABANDONED"
#: Phase 260.1.E — management command ``cleanup_orphan_files`` processed a batch of
#: pre-Phase-260 orphan File rows (no in-tenant Dataset/DQ/Compliance/Governance ref),
#: either dry-run or soft-deleted via ``FileService.delete_file``.
#: ``details_json`` carries: ``tenant_id``, ``count``, ``dry_run``, ``batch``,
#: ``min_age_days``, ``file_ids`` (sample), ``correlation_id``; when
#: ``dry_run`` is false, also ``soft_deleted`` and optional ``failure_sample``.
FILE_ORPHAN_CLEANUP_COMPLETED: str = "FILE_ORPHAN_CLEANUP_COMPLETED"
#: Phase 260.1.F — tenant hard-delete / offboarding: one row per File before
#: the ORM fires DB CASCADE. ``transaction.on_commit`` then enqueues batched
#: RQ jobs that delete ``storage_path`` keys from object storage (paths only).
#:
#: ``details_json`` carries: ``tenant_id``, ``file_id``, ``name``, ``size``,
#: ``content_sha256``, ``storage_path``, ``reason`` (``tenant_hard_delete``).
FILE_TENANT_OFFBOARD_PURGE_SCHEDULED: str = "FILE_TENANT_OFFBOARD_PURGE_SCHEDULED"
#: Phase 260.2.B — ``complete_upload`` rejected: declared MIME incompatible with
#: sniffed magic bytes; object removed from storage. ``details_json`` carries
#: ``declared_content_type``, ``detected_signature`` (when known), ``name``,
#: ``storage_path``, etc.
FILE_FORMAT_MISMATCH_REJECTED: str = "FILE_FORMAT_MISMATCH_REJECTED"
#: Phase 260.2.A — cross-tenant file read attempted without a valid
#: entitlement (or with no asset link to evaluate one). Emitted only after
#: the tenant-scoped queryset would have returned 404 so probes still receive
#: **404** (no existence leak). ``details_json`` carries ``reason`` (e.g.
#: ``NO_ASSET_LINK_FOR_ENTITLEMENT``, ``ENTITLEMENT_DENIED``),
#: ``file_owner_tenant_id``, ``consumer_tenant_id``, optional
#: ``entitlement_error`` (check_entitlement code), and ``file_id``.
FILE_IDOR_ATTEMPT_BLOCKED: str = "FILE_IDOR_ATTEMPT_BLOCKED"
#: Phase 260.2.F — authenticated ``GET /files/{id}/`` returned file metadata
#: (tenant-scoped or entitlement-resolved). Emitted only after **200**;
#: default ~10% deterministic sample, or 100% when
#: ``Tenant.compliance_audit_full_sampling`` is True. ``details_json`` carries
#: ``sampling`` (``full`` | ``ten_percent``), ``file_id``, optional
#: ``consumer_tenant_id`` when the viewer's tenant differs from the file owner.
FILE_METADATA_VIEWED: str = "FILE_METADATA_VIEWED"
#: Phase 260.3.A — user invoked ``GET /datasets/{id}/versions/compare/`` successfully.
#:
#: ``details_json`` carries ``anchor_dataset_id``, ``version1_id``, ``version2_id``,
#: ``change_count``, ``compatibility_level``.
DATASET_VERSION_COMPARED: str = "DATASET_VERSION_COMPARED"
#: Phase 260.3.C — successful ``GET /files/{id}/download/`` after presign issuance.
#:
#: ``details_json`` carries ``name`` (original filename) per existing download audit shape.
FILE_DOWNLOADED: str = "FILE_DOWNLOADED"
#: Phase 260.3.G — client-reported SHA-256 mismatch on a downloaded file.
#:
#: Emitted by ``POST /files/{id}/download/checksum-mismatch/`` when the SDK
#: or browser computes a content hash that differs from the platform-stored
#: ``File.content_sha256``. Fires once per client report; the server never
#: authoritatively decides match/mismatch — the client owns the
#: verification decision and the audit row records what the client said.
#:
#: ``details_json`` carries ``file_id``, ``expected_sha256_prefix`` (first
#: 16 hex chars of ``File.content_sha256``), ``actual_sha256_prefix``
#: (first 16 hex chars of the client-reported value), ``name`` (file
#: name), and ``content_sha256_present`` (False if the file pre-dates
#: SHA-256 capture). Truncating to 16 hex chars gives 64 bits of
#: corruption-fingerprint without persisting the full deterministic
#: hash to general audit-search.
FILE_DOWNLOAD_CHECKSUM_MISMATCH: str = "FILE_DOWNLOAD_CHECKSUM_MISMATCH"
#: Phase 260.4.A.5 — explicit dataset retirement via
#: ``POST /datasets/{id}/retire/``. Distinct from the implicit
#: ``Dataset.status = RETIRED`` flip from Phase 260.1.C (which fires
#: when the backing file is hard-deleted as part of file lifecycle).
#:
#: ``details_json`` carries ``dataset_id``, ``name`` (file name when
#: available), ``format``, ``asset_id`` (or ``null`` for unlinked
#: datasets), and ``retain_until_at`` (the per-tenant retention
#: deadline computed at retire-time so the audit row is self-
#: contained even if the tenant flag changes later).
DATASET_RETIRED: str = "DATASET_RETIRED"
#: Phase 260.4.A.R1 GAP-B — automated hard-deletion of a retired dataset
#: row past its tenant retention window. Emitted by the
#: ``cleanup_retired_datasets`` management command per-tenant-per-run
#: (one summary row carrying the deleted-id list, NOT one row per
#: deleted dataset — bulk sweeps shouldn't flood the audit log).
#:
#: ``details_json`` carries ``tenant_id``, ``window_days``,
#: ``deleted_count``, ``deleted_dataset_ids`` (truncated to the first
#: 100 IDs to keep payload bounded; the count alone is the
#: authoritative deletion telemetry — IDs are for forensic spot-
#: checks).
DATASET_HARD_DELETED_AFTER_RETENTION: str = "DATASET_HARD_DELETED_AFTER_RETENTION"
#: Phase 260.1.F — E2E-gated hard-delete of tenant via
#: ``TenantViewSet.destroy(?cascade=true)`` AFTER per-file offboard audits
#: and queued storage purges from ``tenant_offboard_emit_file_audits_*``.
#:
#: ``details_json`` carries ``slug`` and may carry additional operator context later.
TENANT_HARD_DELETE_CASCADE: str = "TENANT_HARD_DELETE_CASCADE"
#: Phase 260.4.C — display-name change on a File via
#: ``POST /files/{id}/rename/``. Storage path is IMMUTABLE on rename
#: (the object key in S3 / MinIO never moves) — only the
#: human-facing ``File.name`` field changes. Distinct from
#: ``FILE_METADATA_VIEWED`` so audit consumers can filter rename
#: events without scanning a sampled view feed.
#:
#: ``details_json`` carries ``file_id``, ``previous_name``, ``new_name``,
#: ``storage_path`` (proves the storage key did NOT change — the audit
#: row is the durable record that the rename was display-only).
FILE_RENAMED: str = "FILE_RENAMED"
#: Phase 260.4.D — refresh-from-new-file workflow on a dataset via
#: ``POST /datasets/{id}/refresh-from-file/``. A new dataset version
#: is created with the SAME asset FK, a NEW file FK, and
#: ``parent_version`` linked to the source dataset. Distinct from
#: ``DATASET_VERSION_CREATED`` (which the existing ``versions/`` POST
#: emits on schema-only edits) so audit consumers can filter
#: file-replacement events specifically.
#:
#: ``details_json`` carries ``parent_dataset_id``, ``new_dataset_id``,
#: ``new_file_id``, ``parent_file_id`` (or ``null`` if the source had
#: no file), ``new_version`` (the auto-incremented per-asset counter),
#: ``asset_id``, AND ``schema_drift`` — a stable diff dict produced by
#: :class:`SchemaCompareService` against any active Contract linked to
#: the asset.  ``schema_drift.severity`` is ``NONE``/``WARN``/``FAIL``;
#: ``NONE`` when no contract exists OR the new schema matches the
#: contract field-for-field.
DATASET_REFRESHED_FROM_FILE: str = "DATASET_REFRESHED_FROM_FILE"
#: Phase 260.4.E — manual dataset refresh via
#: ``POST /datasets/{id}/refresh/``. Re-runs schema inference on the
#: dataset's EXISTING backing file (same ``file_id``, no version bump
#: unless schema actually changed) and re-computes drift against any
#: active contract. Distinct from ``DATASET_REFRESHED_FROM_FILE``
#: (260.4.D, which uploads a new file) — this audit constant fires
#: ONLY when the refresh re-uses the same file. Operationally similar
#: to a scheduled-run trigger: the user kicks the same pipeline that
#: the platform would have run periodically.
#:
#: ``details_json`` carries ``dataset_id``, ``file_id``, ``asset_id``
#: (or ``null``), ``schema_changed`` (bool — True when the new
#: ``schema_json`` differs from the prior value), ``previous_schema_hash``
#: + ``new_schema_hash`` (SHA-256 hex over canonical JSON; lets
#: audit-replay detect inferred-schema drift without storing the full
#: schema payload), AND ``schema_drift`` — same shape as 260.4.D so
#: audit consumers can dedupe drift handling logic across both
#: refresh paths.
#:
#: TENANT_ADMIN-gated at the view layer so accidental refreshes by
#: regular users can't churn the schema_json + audit log.
DATASET_REFRESH_TRIGGERED: str = "DATASET_REFRESH_TRIGGERED"

#: Phase 260.7.F — scheduled-ingestion source-fetch failure. Emitted
#: when the orchestration layer's source connector
#: (``ScheduledIngestionWorkflow._download_file_task``) cannot fetch a
#: file because the source is unreachable: connector returns non-SUCCESS,
#: connector raises (network timeout, auth failure, 404, bucket
#: missing), or the connector itself isn't registered for the source
#: type. The file is NOT processed; no Dataset / File row is created;
#: the file is marked permanently failed in the run's incremental
#: state via ``DeadLetterQueueManager``.
#:
#: ``details_json`` carries: ``scheduled_ingestion_id``, ``run_id``,
#: ``file_path`` (the source-side path the connector was asked to
#: fetch), ``source_type`` (``S3`` / ``SFTP`` / ``HTTP`` / etc.),
#: ``error_message`` (the str of the underlying exception, truncated
#: to 500 chars to bound the audit-payload size), ``audience``
#: (``"TENANT_ADMIN"`` — the alert is for tenant admins so they can
#: triage source credentials / network reachability).
#:
#: ``result`` is ``"FAILURE"``. The TENANT_ADMIN audience flag is
#: load-bearing for downstream alerting consumers (a future cron, an
#: alerting service) that fan out audit events to email / pager
#: subscriptions per audience tier.
SCHEDULED_INGESTION_SOURCE_UNREACHABLE: str = "SCHEDULED_INGESTION_SOURCE_UNREACHABLE"

#: Phase 260.7.F — scheduled-ingestion empty-data warning. Emitted
#: when the worker successfully downloads + parses a file but the
#: resulting Dataset has ``row_count == 0`` (e.g., a CSV with only a
#: header, or a JSON file with an empty array). The dataset version
#: IS still created (``row_count=0``, ``sample_data_json=[]``) so
#: downstream consumers can see "the source produced an empty
#: snapshot today" rather than "the source is broken" — different
#: operational signals. The audit event surfaces the empty-snapshot
#: condition for ops awareness (e.g., a sales-data feed that
#: suddenly returns zero rows is interesting even if not fatal).
#:
#: Distinct from ``EMPTY_FILE`` (a 0-byte file, which is still a
#: HARD failure at line 71-75 of ``worker_services.py``: zero bytes
#: can't be parsed at all so we can't infer a schema).
#:
#: ``details_json`` carries: ``scheduled_ingestion_id``, ``run_id``,
#: ``dataset_id`` (the just-created version with row_count=0),
#: ``asset_id``, ``file_path``, ``audience`` (``"TENANT_ADMIN"``).
#:
#: ``result`` is ``"WARNING"`` — the run continues; the dataset
#: version is created. Severity-distinct from FAILURE so audit-
#: replay queries can filter on outcome class.
SCHEDULED_INGESTION_EMPTY_DATA_WARN: str = "SCHEDULED_INGESTION_EMPTY_DATA_WARN"

#: Phase 260.7.F — scheduled-ingestion schema-incompatible rejection.
#: Emitted when the worker's inferred schema for a new ingestion does
#: NOT match the prior dataset version's schema for the same asset
#: in a way that breaks consumer contracts. The strict check (260.7.F
#: scope): if the asset has a prior ACTIVE dataset, the new schema's
#: field-name set MUST be a SUPERSET of the prior version's
#: field-name set — i.e., new ingestions can ADD columns (a backward-
#: compatible widening) but MUST NOT remove or rename existing
#: columns (a breaking change for consumers that joined on those
#: fields).
#:
#: When the check fires, the ingestion is REJECTED: the file is
#: marked permanently failed in the incremental state, NO Dataset /
#: File row is created, and TENANT_ADMIN is alerted so the operator
#: can either (a) fix the upstream source schema, (b) explicitly
#: retire the asset before allowing a breaking-schema reset, or (c)
#: introduce a new asset for the changed-shape feed.
#:
#: ``details_json`` carries: ``scheduled_ingestion_id``, ``run_id``,
#: ``asset_id``, ``prior_dataset_id``, ``file_path``, ``missing_fields``
#: (list of field names the new schema removed — REDACTED to first
#: 20 entries per the 240.5.F payload-size cap), ``new_schema_fields``
#: (list — same redaction), ``audience`` (``"TENANT_ADMIN"``).
#:
#: ``result`` is ``"FAILURE"``.
SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED: str = "SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED"

#: Phase 270.A.3 — fired by the marketplace order-create endpoint
#: when a CROSS-TENANT FREE_AUTO_APPROVE order auto-creates an
#: ``AccessRequest`` row in the consumer's tenant with
#: ``status=APPROVED, approved_by=None``. Distinct from
#: ``ACCESS_REQUEST_APPROVED`` (the governance manual-approval audit)
#: so auditor queries scoped to ``action=ACCESS_REQUEST_APPROVED``
#: return ONLY human-approved rows — the load-bearing distinction
#: for compliance reports that need to separate "operator decision"
#: from "system auto-approval".
#:
#: ``details_json`` carries: ``access_request_id``, ``order_id``,
#: ``listing_id``, ``asset_id``, ``consumer_tenant_id``,
#: ``provider_tenant_id``, ``expires_at`` (ISO-8601, 90 days from
#: approval time), ``auto_approved=True`` (redundant for the action
#: name but explicit for downstream consumers reading via
#: ``details_json``).
#:
#: ``result`` is always ``"SUCCESS"`` — the audit row only fires on
#: the happy path (the AccessRequest row was created); a failure on
#: that side effect logs the exception WITHOUT emitting the audit
#: event so the audit log never claims an auto-approval that didn't
#: actually persist.
ACCESS_REQUEST_AUTO_APPROVED: str = "ACCESS_REQUEST_AUTO_APPROVED"

#: Phase 270.A.4 — fired by the marketplace seller-initiated refund
#: endpoint (``POST /api/v1/marketplace/orders/{id}/refund/``) on
#: every successful refund (full or partial). Distinct from the
#: legacy ``PAYMENT_REFUNDED`` action (which fires from the
#: payment-service layer with payment-row context) so auditors
#: querying order-lifecycle events see the refund alongside
#: ``ORDER_APPROVED`` / ``ORDER_FULFILLED`` without joining the
#: payment-transactions table.
#:
#: ``details_json`` carries the spec'd payload:
#: ``order_id`` (str — the refunded order's UUID),
#: ``refund_amount_cents`` (int — amount refunded in this call, in
#: cents), ``type`` (``"full"`` if the refund completed the remaining
#: balance, else ``"partial"``), ``reason`` (operator justification —
#: max 500 chars), ``actor_user_id`` (UUID of the seller-side user
#: OR PLATFORM_ADMIN who issued the refund), ``stripe_refund_id``
#: (the ``re_...`` ID Stripe assigned; the resource-level join key
#: for Stripe-side forensics).
#:
#: ``result`` is always ``"SUCCESS"`` — Stripe-side failures raise
#: BEFORE the audit emission would have fired, so this event records
#: only completed refunds.
ORDER_REFUNDED: str = "ORDER_REFUNDED"

#: Phase 270.B.1 — fired by the Contract post_save signal when a
#: PUBLISHED marketplace ``Listing`` linked to the saved Contract has
#: policy fields (license_summary, intended_use, restricted_use,
#: pricing) that no longer match the Contract's authoritative state.
#: This is the data-marketplace analogue of schema-drift on assets:
#: the listing was published with a SNAPSHOT of the contract's
#: marketplace policy in ``metadata_json``; when the contract
#: changes, that snapshot is stale — and consumers reading the
#: stored listing terms would see one license / use-policy while the
#: provider has actually moved on. The audit row carries the
#: per-key diff so an auditor (or a downstream Bring-Your-Own-Key
#: alerter) can reconstruct WHICH terms drifted without having to
#: read both ``Listing.metadata_json`` AND the Contract row.
#:
#: ``details_json`` payload:
#:   - ``contract_id`` (str): the saved Contract's UUID
#:   - ``contract_version`` (int): per-asset version of the Contract
#:   - ``listing_id`` (str): the affected Listing UUID
#:   - ``drift_diff`` (dict): ``{key: {old, new}}`` for each changed
#:     policy-relevant key. ``old`` is the value previously cached in
#:     the listing's metadata snapshot; ``new`` is the current value
#:     extracted from the contract.
#:   - ``relevant_keys`` (list[str]): the configured allowlist that
#:     drove the comparison (defaults: ``license_summary``,
#:     ``intended_use``, ``restricted_use``, ``pricing``). Settings
#:     override ``MARKETPLACE_DRIFT_RELEVANT_KEYS`` is captured here
#:     so a config flip + a drift fire are both reproducible from
#:     the audit log alone.
#:
#: ``actor_user`` is ``None`` — the signal fires from the contract's
#: save transaction; the actor is whoever saved the contract, but we
#: don't carry the request user across the signal boundary. Operators
#: triaging "who flipped this contract?" should join against the
#: matching ``CONTRACT_UPDATED`` audit row by ``contract_id`` /
#: ``timestamp``.
LISTING_CONTRACT_DRIFT: str = "LISTING_CONTRACT_DRIFT"

#: Phase 270.B.1 — fired when a PUBLISHED listing transitions
#: PUBLISHED → PUBLISHED (a re-publish, idempotent status-wise) AND
#: the listing previously had drift recorded against its linked
#: Contract. The re-publish path refreshes the listing's metadata
#: snapshot from the current Contract policy AND clears
#: ``contract_drift_detected_at`` + ``contract_drift_diff``; this
#: audit row gives ops a single grep-able event for "operator
#: acknowledged the drift and accepted the new terms".
#:
#: ``details_json`` payload:
#:   - ``listing_id`` (str)
#:   - ``contract_id`` (str): the Contract whose policy was applied
#:   - ``cleared_drift_diff`` (dict): the diff that was previously
#:     recorded — captured BEFORE clearing so the audit row is
#:     self-contained
#:   - ``previous_drift_detected_at`` (str ISO-8601): when drift was
#:     first flagged
#:
#: Distinct from ``LISTING_CONTRACT_DRIFT``: this is the
#: ACKNOWLEDGE-AND-CLEAR event, fired by the re-publish path; the
#: drift event itself fires from the Contract post_save signal.
LISTING_REPUBLISHED_AFTER_DRIFT: str = "LISTING_REPUBLISHED_AFTER_DRIFT"

#: Phase 270.B.2.4 — fired by ``revoke_expired_access`` management
#: command when an ``AccessRequest`` whose ``status == PENDING`` has
#: been pending longer than the tenant's
#: ``access_request_pending_sla_days`` SLA. The row is transitioned
#: to ``status=EXPIRED`` and a single audit event records the
#: forced transition.
#:
#: Distinct from the legacy ``ACCESS_EXPIRED_REVOKED`` action which
#: fires for APPROVED requests that crossed their ``expires_at``
#: timestamp — that path REVOKES granted access; this path EXPIRES
#: an unanswered pending request. Operators reading the audit log
#: distinguish "consumer's access was timed out" from "provider
#: never decided" via the action label + the ``previous_status``
#: field in ``details_json``.
#:
#: ``details_json`` payload:
#:   - ``tenant_id`` (str)
#:   - ``access_request_id`` (str): the expired request's UUID
#:   - ``requested_by`` (str): the user who submitted the request
#:   - ``created_at`` (str ISO-8601): when the request was filed
#:   - ``previous_status`` (str): always ``"PENDING"`` for this
#:     action; included so downstream consumers can filter the
#:     SLA-driven path without parsing the action label
#:   - ``sla_days`` (int): the tenant's SLA at the moment the sweep
#:     ran (captured for reproducibility — a later SLA change
#:     can't retroactively reinterpret historic audit rows)
#:   - ``age_days`` (int): how many days the request was pending
#:     when the sweep fired (≥ sla_days by construction)
ACCESS_REQUEST_EXPIRED_BY_SLA: str = "ACCESS_REQUEST_EXPIRED_BY_SLA"

#: Phase 270.D.3 — fired by the ``POST /api/v1/tenants/me/tax-id/``
#: endpoint when a tenant operator submits a new tax registration
#: ID. The endpoint creates / updates the Stripe Customer tax_id;
#: this audit row records the SUBMISSION (verification status is
#: subsequently set via ``TENANT_TAX_ID_VERIFIED`` once Stripe's
#: verification webhook fires).
#:
#: ``details_json`` payload: ``{tax_id_type, tax_id_masked,
#: country, stripe_tax_id_id}``. The plaintext tax_id is NEVER
#: persisted in the audit row — only a masked last-4 form, since
#: PII/PCI-tier handling for tax IDs varies by jurisdiction and
#: the audit log is a wider read-surface than the encrypted
#: ``Tenant.tax_id`` column.
TENANT_TAX_ID_SUBMITTED: str = "TENANT_TAX_ID_SUBMITTED"

#: Phase 270.D.4 — fired by the ``customer.tax_id.verified``
#: Stripe webhook handler when Stripe confirms a previously-
#: submitted tax_id. Flips ``Tenant.tax_id_verified`` to True.
#: Payload: ``{tax_id_type, tax_id_masked, country,
#: stripe_tax_id_id, verified_at}``.
TENANT_TAX_ID_VERIFIED: str = "TENANT_TAX_ID_VERIFIED"

#: Phase 270.D.5 — fired by the ``account.updated`` Stripe webhook
#: handler when Stripe's ``tax_registrations`` for the connected
#: account changes (e.g. a new jurisdiction requires registration
#: because monthly receipts crossed a threshold). The matching
#: Prometheus alert ``StripeTaxRegistrationRequired`` fires off
#: this audit event so ops sees the registration requirement
#: BEFORE the next invoice in that jurisdiction trips Stripe's
#: own tax-collection error.
#:
#: ``details_json`` payload: ``{country, subdivision, threshold,
#: previous_state, current_state, stripe_account_id}``. ``actor``
#: is None — the event originates from Stripe, not a user
#: action.
STRIPE_TAX_REGISTRATION_REQUIRED: str = "STRIPE_TAX_REGISTRATION_REQUIRED"


# ---------------------------------------------------------------------------
# Stripe Connect onboarding (Phase 271.1.5)
# ---------------------------------------------------------------------------

#: Phase 271.1.5 — fired EVERY TIME ``POST /api/v1/billing/connect/
#: onboarding-link/`` returns a hosted Stripe onboarding URL,
#: regardless of whether the underlying Stripe Account was newly
#: created or pre-existed. The link is a one-time-use authenticated
#: URL — auditing each issuance is the only forensic trail for
#: "who got an onboarding link for tenant X, when, and what's its
#: expiry".
#:
#: ``details_json`` carries: ``stripe_account_id`` (hashed for
#: non-admin readers per the audit-redaction pattern), ``expires_at``
#: (the link's expiry unix-seconds), ``account_was_newly_created``
#: (bool — whether this issuance ALSO emitted
#: ``CONNECT_ACCOUNT_CREATED``; lets a forensic reader correlate
#: the two events without joining on stripe_account_id).
CONNECT_ONBOARDING_LINK_ISSUED: str = "CONNECT_ONBOARDING_LINK_ISSUED"

#: Phase 271.1.5 — fired EXACTLY ONCE per Stripe Connect account
#: creation — i.e. the first time the onboarding-link endpoint
#: invokes ``stripe.Account.create()`` for a tenant. Subsequent
#: onboarding-link requests reuse the existing ``stripe_account_id``
#: per the spec ``Express Onboarding Flow`` requirement and MUST
#: NOT re-emit this event.
#:
#: This event is the lifecycle marker for "tenant X started
#: Connect onboarding" — Finance + Support keys off it for first-
#: touch funnel analytics; the ``CONNECT_ONBOARDING_LINK_ISSUED``
#: event below is the per-issuance audit trail.
#:
#: ``details_json`` carries: ``stripe_account_id`` (hashed),
#: ``account_type`` (``EXPRESS`` for MVP), ``country``,
#: ``default_currency``.
CONNECT_ACCOUNT_CREATED: str = "CONNECT_ACCOUNT_CREATED"

# ---------------------------------------------------------------------------
# Stripe Connect webhook events (Phase 271.2)
# ---------------------------------------------------------------------------

#: Phase 271.2 — fired when ``account.updated`` webhook delivers changes
#: to one or more ``ConnectAccount`` cached fields (charges_enabled,
#: payouts_enabled, details_submitted, requirements_json, country,
#: default_currency). Only fires when at least one field actually
#: changed; no-op replays (same values) do NOT emit. ``details_json``
#: carries: ``stripe_account_id``, ``charges_enabled``,
#: ``payouts_enabled``, ``details_submitted``, ``country``,
#: ``default_currency``. ``actor_user`` is None — system event from
#: Stripe webhook.
CONNECT_WEBHOOK_ACCOUNT_UPDATED: str = "CONNECT_WEBHOOK_ACCOUNT_UPDATED"

#: Phase 271.2 — fired when ``account.application.deauthorized``
#: webhook delivers. The connected account has revoked the platform's
#: access. The handler flips ``charges_enabled=False`` /
#: ``payouts_enabled=False`` on the ConnectAccount row. Ops must
#: follow up manually (Stripe-side re-authorization). ``details_json``
#: carries: ``stripe_account_id``. ``result`` is ``"WARNING"`` —
#: deauthorization is always an operational signal, not a failure.
CONNECT_WEBHOOK_ACCOUNT_DEAUTHORIZED: str = "CONNECT_WEBHOOK_ACCOUNT_DEAUTHORIZED"

#: Phase 271.2 — fired when ``capability.updated`` webhook delivers
#: for a Connect account. Records the capability name (e.g.
#: ``card_payments``, ``transfers``), its new status (``active`` /
#: ``inactive`` / ``pending``), and the associated requirements so the
#: KYB review queue (Phase 271.5) can surface stuck capabilities
#: without polling Stripe. ``details_json`` carries:
#: ``stripe_account_id``, ``capability``, ``status``, ``requirements``.
CONNECT_WEBHOOK_CAPABILITY_UPDATED: str = "CONNECT_WEBHOOK_CAPABILITY_UPDATED"

#: Phase 271.2/271.4 — fired when ``payout.created`` webhook delivers
#: for a Connect account. Stub audit trail until the Phase 271.4
#: ``Payout`` model lands. ``details_json`` carries:
#: ``stripe_payout_id``, ``amount``, ``currency``, ``arrival_date``.
CONNECT_WEBHOOK_PAYOUT_CREATED: str = "CONNECT_WEBHOOK_PAYOUT_CREATED"

#: Phase 271.2/271.4 — fired when ``payout.paid`` webhook delivers.
#: Stub audit trail until the Phase 271.4 ``Payout`` model lands.
#: ``details_json`` carries: ``stripe_payout_id``, ``amount``,
#: ``currency``.
CONNECT_WEBHOOK_PAYOUT_PAID: str = "CONNECT_WEBHOOK_PAYOUT_PAID"

#: Phase 271.2/271.4 — fired when ``payout.failed`` webhook delivers.
#: Stub audit trail until the Phase 271.4 ``Payout`` model lands.
#: ``details_json`` carries: ``stripe_payout_id``, ``amount``,
#: ``currency``, ``failure_code``, ``failure_message``. ``result`` is
#: ``"FAILURE"``.
CONNECT_WEBHOOK_PAYOUT_FAILED: str = "CONNECT_WEBHOOK_PAYOUT_FAILED"

# ---------------------------------------------------------------------------
# Phase 272 — Governance ABAC + Multi-Step Approval + Compliance Gate
# ---------------------------------------------------------------------------

#: Phase 272.2 — fired when access request approval is blocked by the
#: compliance gate (no ComplianceRun or allowed_to_store=False).
#: ``details_json`` carries: ``reason``, ``access_request_id``,
#: ``compliance_run_id`` (nullable).
ACCESS_REQUEST_BLOCKED_COMPLIANCE: str = "ACCESS_REQUEST_BLOCKED_COMPLIANCE"

#: Phase 272.2 — fired when a PLATFORM_ADMIN overrides the compliance
#: gate via ``force_approve=true``. ``details_json`` carries:
#: ``access_request_id``, ``compliance_run_id`` (nullable).
ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN: str = (
    "ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN"
)

#: Phase 272.3 — fired every time ABACEngine.evaluate_access() is called
#: during approval. ``details_json`` carries: ``decision`` (PERMIT/DENY),
#: ``policy_id``, ``reason`` (DENY only).
ABAC_DECISION_RECORDED: str = "ABAC_DECISION_RECORDED"

#: Phase 272.4 — fired on each multi-step approval transition.
#: ``details_json`` carries: ``from_step``, ``to_step``,
#: ``approver_id``, ``policy_id``.
ACCESS_REQUEST_STEP_TRANSITIONED: str = "ACCESS_REQUEST_STEP_TRANSITIONED"

#: Phase 272.6 — fired when an approval delegation is created.
APPROVAL_DELEGATION_CREATED: str = "APPROVAL_DELEGATION_CREATED"

#: Phase 272.6 — fired when a delegate exercises their delegation.
APPROVAL_DELEGATION_USED: str = "APPROVAL_DELEGATION_USED"

#: Phase 272.6 — fired when an approval delegation window ends.
APPROVAL_DELEGATION_ENDED: str = "APPROVAL_DELEGATION_ENDED"

# ---------------------------------------------------------------------------
# Phase 273 — Search / SPARQL audit events
# ---------------------------------------------------------------------------

SEARCH_PERFORMED: str = "SEARCH_PERFORMED"
SUGGESTIONS_REQUESTED: str = "SUGGESTIONS_REQUESTED"
SPARQL_EXECUTED: str = "SPARQL_EXECUTED"
RDF_INGESTED: str = "RDF_INGESTED"
SEARCH_RATE_LIMIT_EXCEEDED: str = "SEARCH_RATE_LIMIT_EXCEEDED"
SPARQL_RATE_LIMIT_EXCEEDED: str = "SPARQL_RATE_LIMIT_EXCEEDED"

# ---------------------------------------------------------------------------
# Phase 275 — Warehouse Connectivity audit events
# ---------------------------------------------------------------------------

WAREHOUSE_QUERY_EXECUTED: str = "WAREHOUSE_QUERY_EXECUTED"
WAREHOUSE_INTAKE_STARTED: str = "WAREHOUSE_INTAKE_STARTED"
WAREHOUSE_INTAKE_COMPLETED: str = "WAREHOUSE_INTAKE_COMPLETED"
WAREHOUSE_INTAKE_FAILED: str = "WAREHOUSE_INTAKE_FAILED"
WAREHOUSE_EXPORT_STARTED: str = "WAREHOUSE_EXPORT_STARTED"
WAREHOUSE_EXPORT_COMPLETED: str = "WAREHOUSE_EXPORT_COMPLETED"
WAREHOUSE_EXPORT_FAILED: str = "WAREHOUSE_EXPORT_FAILED"
WAREHOUSE_CIRCUIT_OPEN: str = "WAREHOUSE_CIRCUIT_OPEN"
WAREHOUSE_CIRCUIT_CLOSED: str = "WAREHOUSE_CIRCUIT_CLOSED"
WAREHOUSE_SHARE_ACCESSED: str = "WAREHOUSE_SHARE_ACCESSED"
WAREHOUSE_SCHEMA_DRIFT: str = "WAREHOUSE_SCHEMA_DRIFT"
WAREHOUSE_DQ_SAMPLE_MATERIALIZED: str = "WAREHOUSE_DQ_SAMPLE_MATERIALIZED"
WAREHOUSE_CONNECTION_CREATED: str = "WAREHOUSE_CONNECTION_CREATED"
WAREHOUSE_CONNECTION_UPDATED: str = "WAREHOUSE_CONNECTION_UPDATED"
WAREHOUSE_CONNECTION_DELETED: str = "WAREHOUSE_CONNECTION_DELETED"
WAREHOUSE_CONNECTION_TEST_FAILED: str = "WAREHOUSE_CONNECTION_TEST_FAILED"
WAREHOUSE_CACHE_REFRESHED: str = "WAREHOUSE_CACHE_REFRESHED"

# ---------------------------------------------------------------------------
# Phase 277.B.031 — Billing cost overview
# ---------------------------------------------------------------------------

COST_OVERVIEW_ACCESSED: str = "COST_OVERVIEW_ACCESSED"


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
    "USER_DELETED_UNVERIFIED",
    "MEMBERSHIP_GRANTED",
    "MEMBERSHIP_REVOKED",
    "COMPLIANCE_INTAKE_SCAN_ENQUEUED",
    "COMPLIANCE_INTAKE_GATE_BLOCK",
    "COMPLIANCE_THRESHOLD_EXCEEDED",
    "TENANT_COMPLIANCE_THRESHOLD_CHANGED",
    "COMPLIANCE_GATE_OVERRIDDEN",
    "COMPLIANCE_WEBHOOK_FIRED",
    "COMPLIANCE_EXPORT",
    "COMPLIANCE_RUN_CREATED",
    "COMPLIANCE_RUN_CANCELLED",
    "RESULTS_ACCESSED",
    "COMPLIANCE_SERVICE_UNAVAILABLE",
    "CONSENT_GRANTED",
    "CONSENT_REVOKED",
    "CONSENT_PURPOSE_CHANGED",
    "ROPA_GENERATED",
    "BREACH_INCIDENT_OPENED",
    "BREACH_INCIDENT_STATUS_CHANGED",
    "BREACH_NOTIFICATION_SENT",
    "BREACH_SLA_WARN_WINDOW",
    "BREACH_SLA_CRITICAL_WINDOW",
    "BREACH_SLA_OVERDUE",
    "PROCESSOR_REGISTERED",
    "PROCESSOR_UPDATED",
    "PROCESSOR_AGREEMENT_CREATED",
    "PROCESSOR_AGREEMENT_UPDATED",
    "PROCESSOR_AGREEMENT_SUBPROCESSOR_CHANGED",
    "PROCESSOR_AGREEMENT_EXPIRY_WARN_60",
    "PROCESSOR_AGREEMENT_EXPIRY_WARN_30",
    "PROCESSOR_AGREEMENT_EXPIRY_WARN_7",
    "PROCESSOR_AGREEMENT_EXPIRED",
    "PROCESSOR_AGREEMENT_DELETED",
    "PROCESSOR_REMOVED",
    "DPIA_CREATED",
    "DPIA_SUBMITTED",
    "DPIA_REVIEW_DECISION",
    "DPIA_SUPERSEDED",
    "DPIA_PERIODIC_REVIEW_OPENED",
    "RETENTION_RESOURCE_TOMBSTONED",
    "RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP",
    "RETENTION_POLICY_LEGAL_HOLD_UPDATED",
    "RETENTION_AUTOSWEEP_COMPLETED",
    "AUDIT_EVENT_RETENTION_POLICY_CREATED",
    "AUDIT_EVENT_RETENTION_POLICY_UPDATED",
    "AUDIT_EVENT_RETENTION_POLICY_DELETED",
    "AUDIT_RETENTION_PURGED",
    "AUDIT_INTEGRITY_VERIFIED",
    "AUDIT_INTEGRITY_MISMATCH",
    "AUDIT_GDPR_PURGED",
    "DATA_EXPORT_CREATED",
    "DATA_EXPORT_COMPLETED",
    "SCHEDULED_EXPORT_CREATED",
    "SCHEDULED_EXPORT_UPDATED",
    "SCHEDULED_EXPORT_DELETED",
    "SCHEDULED_EXPORT_TRIGGERED",
    "TENANT_ONBOARDING_STATE_VIEWED",
    "TENANT_CREATED",
    "TENANT_SOFT_DELETED",
    "TENANT_HARD_DELETED",
    "IMPERSONATION_STARTED",
    "IMPERSONATION_ENDED",
    "IMPERSONATION_REJECTED",
    "TENANT_FEATURE_FLAG_CHANGED",
    "FEATURE_FLAG_FLIP_APPROVAL_REQUESTED",
    "FEATURE_FLAG_FLIP_APPROVED",
    "FILE_PURGED",
    "FILE_ORPHAN_DETECTED",
    "FILE_MULTIPART_ABANDONED",
    "FILE_ORPHAN_CLEANUP_COMPLETED",
    "FILE_TENANT_OFFBOARD_PURGE_SCHEDULED",
    "FILE_FORMAT_MISMATCH_REJECTED",
    "FILE_IDOR_ATTEMPT_BLOCKED",
    "FILE_METADATA_VIEWED",
    "DATASET_VERSION_COMPARED",
    "FILE_DOWNLOADED",
    "FILE_DOWNLOAD_CHECKSUM_MISMATCH",
    "DATASET_RETIRED",
    "DATASET_HARD_DELETED_AFTER_RETENTION",
    "TENANT_HARD_DELETE_CASCADE",
    "FILE_RENAMED",
    "DATASET_REFRESHED_FROM_FILE",
    "DATASET_REFRESH_TRIGGERED",
    "SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
    "SCHEDULED_INGESTION_EMPTY_DATA_WARN",
    "SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
    "WEBHOOK_KEY_ROTATED",
    "WEBHOOK_KEY_RETIRED",
    "WEBHOOK_RATE_LIMIT_EXCEEDED",
    "ACCESS_REQUEST_AUTO_APPROVED",
    "ORDER_REFUNDED",
    "LISTING_CONTRACT_DRIFT",
    "LISTING_REPUBLISHED_AFTER_DRIFT",
    "ACCESS_REQUEST_EXPIRED_BY_SLA",
    "TENANT_TAX_ID_SUBMITTED",
    "TENANT_TAX_ID_VERIFIED",
    "STRIPE_TAX_REGISTRATION_REQUIRED",
    "CONNECT_ONBOARDING_LINK_ISSUED",
    "CONNECT_ACCOUNT_CREATED",
    "CONNECT_WEBHOOK_ACCOUNT_UPDATED",
    "CONNECT_WEBHOOK_ACCOUNT_DEAUTHORIZED",
    "CONNECT_WEBHOOK_CAPABILITY_UPDATED",
    "CONNECT_WEBHOOK_PAYOUT_CREATED",
    "CONNECT_WEBHOOK_PAYOUT_PAID",
    "CONNECT_WEBHOOK_PAYOUT_FAILED",
    "ACCESS_REQUEST_BLOCKED_COMPLIANCE",
    "ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN",
    "ABAC_DECISION_RECORDED",
    "ACCESS_REQUEST_STEP_TRANSITIONED",
    "APPROVAL_DELEGATION_CREATED",
    "APPROVAL_DELEGATION_USED",
    "APPROVAL_DELEGATION_ENDED",
    "SEARCH_PERFORMED",
    "SUGGESTIONS_REQUESTED",
    "SPARQL_EXECUTED",
    "RDF_INGESTED",
    "SEARCH_RATE_LIMIT_EXCEEDED",
    "SPARQL_RATE_LIMIT_EXCEEDED",
    "WAREHOUSE_QUERY_EXECUTED",
    "WAREHOUSE_INTAKE_STARTED",
    "WAREHOUSE_INTAKE_COMPLETED",
    "WAREHOUSE_INTAKE_FAILED",
    "WAREHOUSE_EXPORT_STARTED",
    "WAREHOUSE_EXPORT_COMPLETED",
    "WAREHOUSE_EXPORT_FAILED",
    "WAREHOUSE_CIRCUIT_OPEN",
    "WAREHOUSE_CIRCUIT_CLOSED",
    "WAREHOUSE_SHARE_ACCESSED",
    "WAREHOUSE_SCHEMA_DRIFT",
    "WAREHOUSE_DQ_SAMPLE_MATERIALIZED",
    "WAREHOUSE_CONNECTION_CREATED",
    "WAREHOUSE_CONNECTION_UPDATED",
    "WAREHOUSE_CONNECTION_DELETED",
    "WAREHOUSE_CONNECTION_TEST_FAILED",
    "WAREHOUSE_CACHE_REFRESHED",
    # Phase 277.B.031 — Billing cost overview
    "COST_OVERVIEW_ACCESSED",
]
