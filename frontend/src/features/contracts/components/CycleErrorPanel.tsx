/**
 * Phase 228.F2.19 — CycleErrorPanel.
 *
 * Renders a content-rich error state when the server returns a
 * 400 with `code: LINEAGE_CYCLE`.  Shows the offending edge from
 * the response details so the user can locate it in the editor's
 * mapping table.
 */
import { t } from './lineageEditorStrings';

export interface CycleErrorPanelProps {
  edge?: {
    source_contract?: string;
    source_model?: string;
    source_field?: string;
    target_contract?: string;
    target_model?: string;
    target_field?: string;
  };
}

export function CycleErrorPanel({ edge }: CycleErrorPanelProps) {
  return (
    <section
      role="alert"
      data-testid="lineage-cycle-error"
      style={{
        padding: '1rem',
        background: '#fff5f5',
        border: '1px solid #fca5a5',
        borderRadius: 8,
      }}
    >
      <h3>{t('lineage.editor.cycle.title')}</h3>
      <p>{t('lineage.editor.cycle.body')}</p>
      {edge && (
        <pre style={{ marginTop: 8, fontSize: '0.85rem' }}>
          {edge.source_model}.{edge.source_field}
          {' → '}
          {edge.target_model}.{edge.target_field}
        </pre>
      )}
    </section>
  );
}
