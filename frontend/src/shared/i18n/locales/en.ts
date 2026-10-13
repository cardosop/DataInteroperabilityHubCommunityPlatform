/**
 * Phase 228 F5 (228.F5.18) — English translation keys for the
 * lineage time-travel + diff surfaces.
 *
 * Every key is namespaced under `lineage.timetravel.*` /
 * `lineage.diff.*` so a future flatten-and-merge step (when the
 * full i18n library lands) can group keys by feature without
 * collision risk against marketplace / contracts / admin keys.
 */
export const LINEAGE_TIMETRAVEL_EN: Record<string, string> = {
  // ---------- LineageTimeTravelControls ----------
  'lineage.timetravel.controls_aria_label': 'Lineage time-travel controls',
  'lineage.timetravel.as_of_label': 'As of',
  'lineage.timetravel.as_of_help': 'Render lineage at this exact moment.',
  'lineage.timetravel.version_label': 'Version',
  'lineage.timetravel.version_placeholder': '— pick a version —',
  'lineage.timetravel.apply': 'Apply',
  'lineage.timetravel.apply_aria': 'Apply time-travel anchor',
  'lineage.timetravel.reset': 'Reset',
  'lineage.timetravel.reset_aria': 'Reset to live view',

  // ---------- LineageDiffView ----------
  // Spec REQ-LIN-F5-002: ``modified`` is always empty under SCD-2
  // close-and-reopen, so the UI surfaces only added/removed/unchanged
  // buckets. The ``modified.*`` key is kept for forward-compatible
  // clients that read the empty list.
  'lineage.diff.added': 'Added',
  'lineage.diff.removed': 'Removed',
  'lineage.diff.unchanged': 'Unchanged',
  'lineage.diff.modified': 'Modified',
  'lineage.diff.heading': 'Lineage diff',
  'lineage.diff.summary': 'Summary:',
  'lineage.diff.from': 'from',
  'lineage.diff.to': 'to',
  'lineage.diff.loading': 'Loading lineage diff…',
  'lineage.diff.error': 'Failed to load diff:',
  'lineage.diff.no_anchor': 'Pick two anchors to compute a diff.',
  'lineage.diff.empty_bucket': '— no edges in this bucket —',
};

/**
 * Phase 250.2.B.5 — English copy for the schema-drift banner shown
 * inline on the asset-creation success summary. The keys live under
 * ``assets.schema_drift.*`` so a future per-feature locale split
 * doesn't collide with the lineage-diff strings above.
 *
 * Copy is UX-writer drafted: short noun phrases for headings, full
 * sentences for explanatory body text. Avoid jargon ("structural
 * incompatibility" → "Schema does not match the contract"). All
 * strings are screen-reader friendly — no decorative-only icons,
 * no truncation that hides meaning.
 */
export const ASSETS_SCHEMA_DRIFT_EN: Record<string, string> = {
  // ---------- Severity headings ----------
  'assets.schema_drift.heading.warn': 'Schema drift detected',
  'assets.schema_drift.heading.fail': 'Schema does not match the contract',

  // ---------- Severity body copy ----------
  'assets.schema_drift.body.warn':
    'The dataset has columns the contract does not declare, or types that are wider than required. The asset was still created — review the differences below and update the contract if needed.',
  'assets.schema_drift.body.fail':
    'The dataset is missing fields the contract requires, or has incompatible types. The asset was still created so you can fix the data, but downstream consumers that rely on the contract will see errors until the schema matches.',

  // ---------- Section headings (3 categories) ----------
  'assets.schema_drift.section.missing': 'Missing fields',
  'assets.schema_drift.section.missing_help':
    'Declared by the contract, not present in the dataset.',
  'assets.schema_drift.section.extra': 'Extra fields',
  'assets.schema_drift.section.extra_help': 'Present in the dataset, not declared by the contract.',
  'assets.schema_drift.section.mismatches': 'Type mismatches',
  'assets.schema_drift.section.mismatches_help':
    'Same field name, different type. Marked compatible if the dataset type is a safe widening of the contract type.',

  // ---------- Type-mismatch table ----------
  'assets.schema_drift.mismatch_col.field': 'Field',
  'assets.schema_drift.mismatch_col.contract_type': 'Contract type',
  'assets.schema_drift.mismatch_col.dataset_type': 'Dataset type',
  'assets.schema_drift.mismatch_col.compatible': 'Compatible?',
  'assets.schema_drift.mismatch.compatible_yes': 'Yes — safe widening',
  'assets.schema_drift.mismatch.compatible_no': 'No',

  // ---------- Empty / collapsed states ----------
  'assets.schema_drift.empty_section': '— none —',
  'assets.schema_drift.collapsed_count': '{count} item(s) — expand to see details',

  // ---------- ARIA labels ----------
  'assets.schema_drift.banner_aria_label': 'Schema drift report for the new asset',
};

/**
 * Phase 250.6.B.5 — English copy for the AssetTypePickerStep.
 *
 * UX-writer-drafted copy: each option pairs a 1-line title with
 * a 1-sentence body that names the user's intent (NOT the
 * backend mechanism) so a non-engineer reader can self-route.
 * The ``aria_label`` keys carry the verbose accessible name for
 * NVDA / VoiceOver — required for WCAG 2.1 AA per Phase
 * 250.6.B.4.
 */
export const ASSETS_TYPE_PICKER_EN: Record<string, string> = {
  // ---------- Step header ----------
  'assets.type_picker.heading': 'What are you bringing to the catalog?',
  'assets.type_picker.body':
    'Pick the option that matches what you have in hand. We pre-configure the next step around your choice — you can always change later.',
  'assets.type_picker.aria_label': 'Choose the type of asset you are creating',
  'assets.type_picker.skip_label': 'Skip and configure manually',

  // ---------- Option: data ----------
  'assets.type_picker.option.data.title': 'A data file',
  'assets.type_picker.option.data.body':
    'Upload a CSV / JSON / Parquet file. We infer the schema and run quality + compliance checks before publishing.',
  'assets.type_picker.option.data.aria_label': 'Create asset from a data file',

  // ---------- Option: contract ----------
  'assets.type_picker.option.contract.title': 'A contract document',
  'assets.type_picker.option.contract.body':
    'Upload an ODCS or DataContract.com YAML / JSON. Catalog the spec without uploading data.',
  'assets.type_picker.option.contract.aria_label': 'Create asset from a contract document',

  // ---------- Option: both ----------
  'assets.type_picker.option.both.title': 'Both — file + contract',
  'assets.type_picker.option.both.body':
    'Upload a data file AND its contract. We validate the data conforms to the contract before publishing.',
  'assets.type_picker.option.both.aria_label':
    'Create asset from both a data file and a contract document',

  // ---------- Option: metadata ----------
  'assets.type_picker.option.metadata.title': 'Metadata only',
  'assets.type_picker.option.metadata.body':
    'Reference an external data source. Catalog the asset without uploading anything to the hub.',
  'assets.type_picker.option.metadata.aria_label':
    'Create asset with metadata only — no upload, no contract',

  // ---------- 250.6.D.3 — onboarding-incomplete variant ----------
  // Rendered INSTEAD of the four cards when the runtime capability
  // ``asset_creation_blocked_reason === "ONBOARDING_INCOMPLETE"``.
  // Copy is outcome-language ("Complete onboarding to start
  // creating assets") not platform-jargon ("KYC submission
  // required"); UX-writer brief is to keep the user moving toward
  // the onboarding flow with one clear next step.
  'assets.type_picker.onboarding_incomplete.heading': 'Finish onboarding to start creating assets',
  'assets.type_picker.onboarding_incomplete.body':
    'Asset creation unlocks once your tenant admin is invited, KYC is submitted, and billing is set up. Complete the remaining steps to continue.',
  'assets.type_picker.onboarding_incomplete.cta': 'Complete onboarding',
};

/**
 * Phase 250.3.A.3 — English copy for the marketplace publish-page
 * KYC remediation banner. The keys live under
 * ``marketplace.publish.kyc_*`` so a future per-feature locale split
 * doesn't collide with assets / lineage strings above.
 *
 * The copy is operator-actionable: a heading that names the
 * blocker, a body that explains what to do, and a call-to-action
 * link to ``/settings/billing/kyc`` (the canonical KYC
 * verification surface). Screen-reader friendly — no decorative
 * icons, no truncation that hides meaning.
 */
/**
 * Databricks control plane (openspec add-databricks-control-plane task 0.18)
 * — workspace management page + guided registration wizard keys, namespaced
 * under ``databricks.*``. Consumed via the useTranslation shim.
 */
export const DATABRICKS_EN: Record<string, string> = {
  'databricks.page.title': 'Databricks workspaces',
  'databricks.page.loading': 'Loading Databricks workspaces…',
  'databricks.page.empty': 'No Databricks workspaces registered yet.',
  'databricks.page.register_cta': 'Register workspace',
  'databricks.page.back_to_workspaces': '← Back to workspaces',
  'databricks.page.flag_disabled_body':
    'The Databricks control plane is disabled for this tenant. Contact your platform administrator to enable it.',
  'databricks.page.test_action': 'Test',
  'databricks.page.testing': 'Testing...',

  'databricks.wizard.step_register_title': 'Register Databricks workspace',
  'databricks.wizard.name_label': 'Workspace name',
  'databricks.wizard.host_label': 'Workspace host',
  'databricks.wizard.cloud_label': 'Cloud',
  'databricks.wizard.region_label': 'Region',
  'databricks.wizard.metastore_label': 'Metastore ID (optional)',


  'databricks.warehouses.title': 'SQL warehouses',
  'databricks.warehouses.loading': 'Loading SQL warehouses…',
  'databricks.warehouses.empty': 'No SQL warehouses reported for this workspace yet.',
  'databricks.warehouses.name': 'Name',
  'databricks.warehouses.state': 'State',
  'databricks.warehouses.type': 'Type',
  'databricks.warehouses.size': 'Size',
  'databricks.warehouses.actions': 'Actions',
  'databricks.warehouses.serverless': 'serverless',
  'databricks.warehouses.classic': 'classic',
  'databricks.warehouses.start': 'Start',
  'databricks.warehouses.stop': 'Stop',
  'databricks.warehouses.refresh': 'Refresh',
  'databricks.jobs.title': 'Databricks jobs',
  'databricks.jobs.loading': 'Loading Databricks jobs…',
  'databricks.jobs.empty': 'No jobs reported for this workspace yet.',
  'databricks.jobs.name': 'Name',
  'databricks.jobs.schedule': 'Schedule',
  'databricks.jobs.tasks': 'Tasks',
  'databricks.jobs.actions': 'Actions',
  'databricks.jobs.scheduled': 'scheduled',
  'databricks.jobs.unscheduled': 'unscheduled',
  'databricks.jobs.view_runs': 'View runs',
  'databricks.jobs.hide_runs': 'Hide runs',
  'databricks.jobs.runs_title': 'Job runs',
  'databricks.jobs.runs_loading': 'Loading runs…',
  'databricks.jobs.runs_empty': 'No runs reported for this job yet.',
  'databricks.jobs.run_id': 'Run id',
  'databricks.jobs.lifecycle_state': 'Lifecycle state',
  'databricks.jobs.result_state': 'Result',
  'databricks.jobs.duration': 'Duration (ms)',
  'databricks.jobs.refresh': 'Refresh',
  'databricks.wizard.registering': 'Registering...',
  'databricks.wizard.continue': 'Continue',

  'databricks.wizard.step_credentials_title': 'Connect your app',
  'databricks.wizard.instructions_body':
    'In the Databricks workspace console, generate a personal access token (Settings → Developer → Access tokens) or register an OAuth M2M client (service principal). The Hub stores the credential encrypted at rest and never returns it.',
  'databricks.wizard.auth_mode_label': 'Auth mode',
  'databricks.wizard.auth_mode_pat': 'Personal Access Token (PAT)',
  'databricks.wizard.auth_mode_m2m': 'OAuth M2M (client credentials)',
  'databricks.wizard.token_label': 'Personal access token',
  'databricks.wizard.client_id_label': 'Client ID',
  'databricks.wizard.client_secret_label': 'Client secret',
  'databricks.wizard.attaching': 'Attaching...',
  'databricks.wizard.attach_credential': 'Attach credential',
  'databricks.wizard.change_credential': 'Change credential',

  'databricks.wizard.step_test_title': 'Test connection',
  'databricks.wizard.test_body':
    'The Hub probes the workspace with the stored credential. A healthy workspace becomes ACTIVE.',
  'databricks.wizard.testing': 'Testing...',
  'databricks.wizard.retry_test': 'Retry test',

  'databricks.sso.cta': 'Continue with Databricks',
  'databricks.sso.busy': 'Connecting…',
  'databricks.sso.no_workspaces': 'No Databricks workspace is available for sign-in.',
  'databricks.sso.chooser_title': 'Choose a Databricks workspace',
  'databricks.sso.chooser_loading': 'Loading workspaces…',
  'databricks.sso.chooser_cancel': 'Cancel',
  'databricks.sso.countdown_body': 'Databricks access needs re-verification soon.',
  'databricks.sso.countdown_minutes': 'min remaining',

  // databricks catalog browser (1.9)
  'databricks.catalog.browse_cta': 'Browse catalog',
  'databricks.catalog.root_crumb': 'Catalog',
  'databricks.catalog.breadcrumbs_label': 'Catalog breadcrumbs',
  'databricks.catalog.search_label': 'Search the current listing',
  'databricks.catalog.search_placeholder': 'Search by name…',
  'databricks.catalog.kind_tabs': 'Object kind',
  'databricks.catalog.loading': 'Loading…',
  'databricks.catalog.list_label': 'Catalog objects',
  'databricks.catalog.empty': 'No objects found.',
  'databricks.catalog.detail_label': 'Table detail',
  'databricks.catalog.detail_owner': 'Owner',
  'databricks.catalog.detail_type': 'Type',
  'databricks.catalog.detail_columns': 'Columns',
  'databricks.catalog.detail_permissions': 'My effective permissions',
  'databricks.catalog.detail_no_permissions': 'None',
  'databricks.budgets.title': 'Databricks cost budgets',
  'databricks.budgets.loading': 'Loading cost budgets…',
  'databricks.budgets.empty': 'No cost budgets configured yet.',
  'databricks.budgets.refresh': 'Refresh',
  'databricks.budgets.scope': 'Scope',
  'databricks.budgets.mode': 'Mode',
  'databricks.budgets.rolling_hour': 'Rolling hour',
  'databricks.budgets.breakdown': 'Per-warehouse breakdown',
  'databricks.budgets.tenant_scope': 'Tenant-wide',
  'databricks.budgets.unlimited': 'Unlimited',
  'databricks.budgets.progress_label': 'Rolling-hour budget consumption',
  'databricks.budgets.units': 'units',
  'databricks.budgets.no_breakdown': 'No warehouse activity in the rolling hour',
  'databricks.budgets.unattributed': 'Unattributed',
};

export const MARKETPLACE_PUBLISH_KYC_EN: Record<string, string> = {
  'marketplace.publish.kyc_blocked.heading': 'KYC verification required to publish',
  'marketplace.publish.kyc_blocked.body':
    'Your tenant must complete KYC verification before any listing can go live in the marketplace catalogue. The draft has been saved — once verification clears, you can publish without re-entering details.',
  'marketplace.publish.kyc_blocked.cta_label': 'Verify KYC now',
  'marketplace.publish.kyc_blocked.status_label': 'Current KYC status:',
  'marketplace.publish.kyc_blocked.aria_label': 'KYC verification required to publish listing',
};

/**
 * close-test-coverage-gaps 2.4 — English copy for the unified approval
 * inbox. The populated-inbox E2E run exposed these keys rendering RAW
 * ("governance.approvalInbox.title 41") — the component shipped before
 * its locale table. Namespaced under ``governance.approvalInbox.*`` for
 * the future per-feature locale split.
 */
export const GOVERNANCE_APPROVAL_INBOX_EN: Record<string, string> = {
  'governance.approvalInbox.title': 'My Approvals',
  'governance.approvalInbox.empty': 'No pending approval items',
  'governance.approvalInbox.view_all': 'View all',
  'governance.approvalInbox.select_all': 'Select all',
  'governance.approvalInbox.reject_reason': 'Reject reason…',
  'governance.approvalInbox.approve': 'Approve',
  'governance.approvalInbox.reject': 'Reject',
};

/**
 * close-test-coverage-gaps 4.4 — English copy for the governance
 * compliance surfaces (DSAR handler queue/detail, breach register,
 * processor agreements). The DSAR pages render these keys WITHOUT
 * inline fallbacks, so until this table shipped the English UI showed
 * RAW KEYS ("governance.dsar.queue_title") — the same family as the
 * 2.4 approval-inbox incident. The breach/processor entries mirror the
 * components' inline fallbacks so the eventual fallback removal stays
 * lossless; translations were reconciled against
 * locales/pt.ts (governance.dsar.*).
 */
export const GOVERNANCE_COMPLIANCE_EN: Record<string, string> = {
  // ── DSAR handler queue + detail ────────────────────────────────────
  'governance.dsar.queue_title': 'Data subject requests (DSAR)',
  'governance.dsar.col_type': 'Type',
  'governance.dsar.col_subject': 'Email',
  'governance.dsar.col_status': 'Status',
  'governance.dsar.col_sla_scan': 'SLA level',
  'governance.dsar.col_deadline': 'Fulfilment deadline (UTC)',
  'governance.dsar.col_fulfil_detail': 'Fulfilment clock',
  'governance.dsar.col_action': 'Action',
  'governance.dsar.countdown_prefix':
    'Time remaining until the statutory fulfilment deadline',
  'governance.dsar.countdown_overdue': 'Statutory fulfilment deadline exceeded',
  'governance.dsar.subject_tz_label': "Subject's local time",
  'governance.dsar.regulator_tz_label': "Regulator's local time",
  'governance.dsar.open': 'Open',
  'governance.dsar.empty': 'No DSAR requests in this tenant.',
  'governance.dsar.detail_title': 'DSAR request detail',
  'governance.dsar.loading': 'Loading…',
  'governance.dsar.btn_materialize': 'Build response package',
  'governance.dsar.btn_reject': 'Reject',
  'governance.dsar.btn_legal_hold': 'Legal hold',
  'governance.dsar.btn_download': 'Issue download URL (24h)',
  'governance.dsar.download_ready':
    'Pre-signed download URL (copy promptly; it may expire):',
  'governance.dsar.prompt_reject': 'Rejection reason (visible on the audit trail)',
  'governance.dsar.prompt_hold_reason': 'Legal-hold reason (optional)',

  // ── Breach register / templates (mirrors component fallbacks) ──────
  'governance.breach.dashboard_title': 'Breach response dashboard',
  'governance.breach.open_count': 'Open incidents',
  'governance.breach.pending_notifications': 'Pending notifications',
  'governance.breach.col_title': 'Title',
  'governance.breach.col_status': 'Status',
  'governance.breach.col_deadline': 'Supervisory deadline (UTC)',
  'governance.breach.col_countdown': 'Countdown',
  'governance.breach.col_action': 'Action',
  'governance.breach.view': 'View',
  'governance.breach.btn_contained': 'Mark contained',
  'governance.breach.btn_notified': 'Mark notified',
  'governance.breach.btn_closed': 'Close',
  'governance.breach.not_found': 'Not found',
  'governance.breach.notifications': 'Notifications',
  'governance.breach.notif_due': 'Regime supervisory due (UTC)',
  'governance.breach.countdown_overdue': 'OVERDUE',
  'governance.breach.btn_mark_sent': 'Record as sent + proof',
  'governance.breach.prompt_outbound_ref': 'Outbound reference (ticket id)',
  'governance.breach.templates_title': 'Breach notification templates',
  'governance.breach.templates_intro':
    'Merged view: platform defaults plus tenant overrides. Placeholders: $incident_title, $incident_summary, $authority_name, $regime, $deadline_utc.',
  'governance.breach.field_regime': 'Regime',
  'governance.breach.field_subject': 'Subject',
  'governance.breach.field_body': 'Body',
  'governance.breach.save': 'Save tenant override',
  'governance.breach.saving': 'Saving…',
  'governance.breach.report_title': 'Report a personal data breach',
  'governance.breach.field_title': 'Title',
  'governance.breach.field_summary': 'Summary (no unnecessary personal data)',
  'governance.breach.field_regimes': 'Regimes (comma-separated)',
  'governance.breach.submit': 'Open incident',
  'governance.breach.submitting': 'Submitting…',

  // ── Processor agreements ────────────────────────────────────────────
  'governance.processors.title': 'Processor agreements',
  'governance.processors.add_processor': 'Add processor',
  'governance.processors.legal_name': 'Legal name (optional)',
  'governance.processors.list': 'Processors',
  'governance.processors.name': 'Name',
  'governance.processors.save': 'Save',
  'governance.processors.saving': 'Saving…',
};

/**
 * Aggregated English locale object merging all per-feature *_EN
 * constants into a single lookup. Consumers that need the full
 * bundle can import this one constant instead of piecing together
 * individual exports.
 */
export const ALL_I18N_EN: Record<string, string> = {
  ...LINEAGE_TIMETRAVEL_EN,
  ...ASSETS_SCHEMA_DRIFT_EN,
  ...ASSETS_TYPE_PICKER_EN,
  ...MARKETPLACE_PUBLISH_KYC_EN,
  ...DATABRICKS_EN,
  ...GOVERNANCE_APPROVAL_INBOX_EN,
  ...GOVERNANCE_COMPLIANCE_EN,

  // ═══ PUBLIC LEGAL (restored 2.4a — production pages consume these) ═══
  'public.legal.home.title': 'Legal & transparency',
  'public.legal.home.intro':
    'These pages summarise how the Meshant platform treats personal data. They do not replace the data-processing agreement in your organisation’s contract.',
  'public.legal.home.privacy_link': 'Privacy notice',
  'public.legal.home.subprocessors_link': 'Subprocessors',
  'public.legal.home.dpia_link': 'Transfer summary / DPIA',
  'public.legal.home.dsar_link': 'Exercise your data-subject rights (DSAR)',
  'public.legal.privacy.title': 'Platform privacy notice',
  'public.legal.privacy.body':
    'Meshant processes tenant configuration, authentication identifiers, billing contacts, and the operational telemetry needed to run the hub. Aggregated telemetry excludes raw data-subject content; avoid placing personal data in URLs or ticket bodies. Personal data you upload stays within your tenant boundary with row-level isolation. High-risk flows (federation, backups, marketplaces) are described in the transfer/DPIA summary.',
  'public.legal.subprocessors.title': 'Subprocessor summary',
  'public.legal.subprocessors.body':
    'Representative infrastructure processors include object storage (e.g. Amazon S3) for artifacts and exports, and transactional email (e.g. Amazon SES) for DSAR one-time codes and legal notices. Identity verification may be delegated to an IDV partner when that capability is enabled; the provider name will appear here and in your DPA addendum. Tenant-specific connector processors are listed in your RoPA.',
  'public.legal.dpia.title': 'Transfer impact and DPIA summary',
  'public.legal.dpia.body':
    'High-risk workflows (billing, SSO, federation, backups) undergo periodic privacy reviews. Recursive DPIAs are maintained per subsystem; artifacts are disclosed to authorised customer legal contacts under NDA.',
};
