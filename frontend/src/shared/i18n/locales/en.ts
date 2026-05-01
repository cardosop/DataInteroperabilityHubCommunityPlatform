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
