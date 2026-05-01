/**
 * Phase 228.F2.19 — CycleErrorPanel.
 *
 * Renders a content-rich error state when the server returns a
 * 400 with `code: LINEAGE_CYCLE`.  Shows the offending edge from
 * the response details so the user can locate it in the editor's
 * mapping table.
 */
import { t } from './lineageEditorStrings';
import './CycleErrorPanel.css';

export interface CycleErrorPanelProps {
  edge?: {
    source_contract?: string;
    source_model?: string;
    source_field?: string;
    target_contract?: string;
    target_model?: string;
    target_field?: string;
  };
  // REQ-LIN-F2-002 — cycle path as a closed-loop list of node ids
  // ("contract_id:model.field"); first == last.  Server now returns
  // this as `details.cycle` per the spec scenario.
  cycle?: string[];
}

export function CycleErrorPanel({ edge, cycle }: CycleErrorPanelProps) {
  return (
    <section
      role="alert"
      className="lineage-cycle-error"
      data-testid="lineage-cycle-error"
    >
      <h3>{t('lineage.editor.cycle.title')}</h3>
      <p>{t('lineage.editor.cycle.body')}</p>
      {cycle && cycle.length > 0 && (
        <pre
          className="lineage-cycle-error__detail"
          data-testid="lineage-cycle-path"
        >
          {cycle.join(' → ')}
        </pre>
      )}
      {!cycle && edge && (
        <pre className="lineage-cycle-error__detail">
          {edge.source_model}.{edge.source_field}
          {' → '}
          {edge.target_model}.{edge.target_field}
        </pre>
      )}
    </section>
  );
}
