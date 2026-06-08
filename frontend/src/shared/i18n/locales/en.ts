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
  'assets.schema_drift.section.extra_help':
    'Present in the dataset, not declared by the contract.',
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
  'assets.schema_drift.collapsed_count':
    '{count} item(s) — expand to see details',

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
  'assets.type_picker.aria_label':
    'Choose the type of asset you are creating',
  'assets.type_picker.skip_label': 'Skip and configure manually',

  // ---------- Option: data ----------
  'assets.type_picker.option.data.title': 'A data file',
  'assets.type_picker.option.data.body':
    'Upload a CSV / JSON / Parquet file. We infer the schema and run quality + compliance checks before publishing.',
  'assets.type_picker.option.data.aria_label':
    'Create asset from a data file',

  // ---------- Option: contract ----------
  'assets.type_picker.option.contract.title': 'A contract document',
  'assets.type_picker.option.contract.body':
    'Upload an ODCS or DataContract.com YAML / JSON. Catalog the spec without uploading data.',
  'assets.type_picker.option.contract.aria_label':
    'Create asset from a contract document',

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
  'assets.type_picker.onboarding_incomplete.heading':
    'Finish onboarding to start creating assets',
  'assets.type_picker.onboarding_incomplete.body':
    'Asset creation unlocks once your tenant admin is invited, KYC is submitted, and billing is set up. Complete the remaining steps to continue.',
  'assets.type_picker.onboarding_incomplete.cta':
    'Complete onboarding',
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
export const MARKETPLACE_PUBLISH_KYC_EN: Record<string, string> = {
  'marketplace.publish.kyc_blocked.heading':
    'KYC verification required to publish',
  'marketplace.publish.kyc_blocked.body':
    'Your tenant must complete KYC verification before any listing can go live in the marketplace catalogue. The draft has been saved — once verification clears, you can publish without re-entering details.',
  'marketplace.publish.kyc_blocked.cta_label': 'Verify KYC now',
  'marketplace.publish.kyc_blocked.status_label': 'Current KYC status:',
  'marketplace.publish.kyc_blocked.aria_label':
    'KYC verification required to publish listing',
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
};
