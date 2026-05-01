/**
 * Phase 228.F2.31 (REQ-LIN-X-001) — namespaced i18n strings for the
 * field-level lineage editor.
 *
 * Every customer-visible string in the LineageEditPage / modals /
 * cycle panel is sourced from this module under the
 * `lineage.editor.*` key namespace.
 */

export const lineageEditorStrings = {
  // Page chrome
  'lineage.editor.title': 'Edit lineage',
  'lineage.editor.subtitle': 'Map source fields to target fields. Save to commit; the server validates cycles, missing fields, and type compatibility.',

  // Toolbar
  'lineage.editor.toolbar.add_edge': 'Add edge',
  'lineage.editor.toolbar.save': 'Save changes',
  'lineage.editor.toolbar.cancel': 'Cancel',
  'lineage.editor.toolbar.dirty_indicator': 'Unsaved changes',

  // Source / target panes
  'lineage.editor.pane.source.heading': 'Source fields',
  'lineage.editor.pane.target.heading': 'Target fields',
  'lineage.editor.pane.empty': 'No fields declared. Open the Schema editor on the contract to add fields first.',
  'lineage.editor.pane.search': 'Search fields…',

  // Edges table
  'lineage.editor.edges.heading': 'Mapping',
  'lineage.editor.edges.col.source': 'Source',
  'lineage.editor.edges.col.target': 'Target',
  'lineage.editor.edges.col.type': 'Type',
  'lineage.editor.edges.col.actions': 'Actions',
  'lineage.editor.edges.empty': 'No edges yet. Click a source field then a target field to map them.',
  'lineage.editor.edges.row.edit': 'Edit',
  'lineage.editor.edges.row.remove': 'Remove',

  // Edge detail modal
  'lineage.editor.edge_modal.title': 'Edge detail',
  'lineage.editor.edge_modal.field.source_model': 'Source model',
  'lineage.editor.edge_modal.field.source_field': 'Source field',
  'lineage.editor.edge_modal.field.target_model': 'Target model',
  'lineage.editor.edge_modal.field.target_field': 'Target field',
  'lineage.editor.edge_modal.field.edge_type': 'Edge type',
  'lineage.editor.edge_modal.field.transformation_ref': 'Transformation reference',
  'lineage.editor.edge_modal.field.job_ref': 'Job reference',
  'lineage.editor.edge_modal.save': 'Save edge',
  'lineage.editor.edge_modal.cancel': 'Cancel',

  // Cycle error panel
  'lineage.editor.cycle.title': 'Cycle detected',
  'lineage.editor.cycle.body': "This mapping would create a circular dependency. Lineage graphs must be acyclic — review the highlighted edges and remove the loop before saving.",

  // 412 conflict modal
  'lineage.editor.conflict.title': 'Lineage was edited by someone else',
  'lineage.editor.conflict.body': 'Your changes are preserved as a draft. Reload to see the latest lineage and merge your edits.',
  'lineage.editor.conflict.reload': 'Reload and merge',
  'lineage.editor.conflict.discard': 'Discard my changes',

  // 413 cap
  'lineage.editor.too_large.title': 'Too many edges',
  'lineage.editor.too_large.body': 'Lineage edits cannot exceed 1000 edges per save. Split your changes into multiple saves.',

  // Validation surface
  'lineage.editor.validation.field_not_found.title': 'Unknown field',
  'lineage.editor.validation.field_not_found.body': 'One of your edges references a field that doesn’t exist on the contract. Check the source/target field names.',
  'lineage.editor.validation.type_mismatch.title': 'Type incompatibility',
  'lineage.editor.validation.type_mismatch.body': 'Source and target field types are incompatible without an explicit transformation. Add a transformation reference or change the field selection.',

  // Loading / save states
  'lineage.editor.saving': 'Saving…',
  'lineage.editor.save_success': 'Lineage saved',
  'lineage.editor.save_error': 'Save failed',
} as const;

export type LineageEditorStringKey = keyof typeof lineageEditorStrings;

export function t(key: LineageEditorStringKey): string {
  return lineageEditorStrings[key];
}
