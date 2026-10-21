/**
 * Phase 228 F5 (228.F5.13 + F5.16) — diff view (spec-aligned).
 *
 * Renders the three diff buckets returned by the API:
 * `added` / `removed` / `unchanged`. Per REQ-LIN-F5-002 the
 * response also carries `modified: []` (always empty, because
 * SCD-2 represents modifications as close-and-reopen) — we
 * surface it in the summary count for completeness but render no
 * bucket for it.
 *
 * Color-blind accessibility (228.F5.16 / REQ-LIN-X-002): each
 * bucket carries 3 redundant channels:
 *
 *   1. color (palette safe for protanopia + deuteranopia),
 *   2. icon glyph (`+ − =`),
 *   3. explicit text label.
 *
 * The glyph uses `aria-hidden="true"` so screen readers don't
 * double-announce.
 */
import type { LineageDiff, LineageDiffEdge } from '../../../shared/types/lineage';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import styles from './LineageDiffView.module.css';

export interface LineageDiffViewProps {
  diff: LineageDiff | null;
  isLoading?: boolean;
  error?: Error | null;
}

interface BucketStyle {
  className: string;
  glyph: string;
  testid: string;
  labelKey: string;
  fallback: string;
}

const BUCKET_STYLES: Record<'added' | 'removed' | 'unchanged', BucketStyle> = {
  added: {
    className: styles.bucketAdded,
    glyph: '+',
    testid: 'lineage-diff-added',
    labelKey: 'lineage.diff.added',
    fallback: 'Added',
  },
  removed: {
    className: styles.bucketRemoved,
    glyph: '−',
    testid: 'lineage-diff-removed',
    labelKey: 'lineage.diff.removed',
    fallback: 'Removed',
  },
  unchanged: {
    className: styles.bucketUnchanged,
    glyph: '=',
    testid: 'lineage-diff-unchanged',
    labelKey: 'lineage.diff.unchanged',
    fallback: 'Unchanged',
  },
};

function formatEdgeLabel(edge: LineageDiffEdge): string {
  const src = edge.source_contract ? edge.source_contract.slice(0, 8) : '∅';
  const tgt = edge.target_contract ? edge.target_contract.slice(0, 8) : '∅';
  const srcField = edge.source_field ? `.${edge.source_field}` : '';
  const tgtField = edge.target_field ? `.${edge.target_field}` : '';
  return `${src}${srcField} → ${tgt}${tgtField} [${edge.edge_type}]`;
}

export function LineageDiffView({ diff, isLoading, error }: LineageDiffViewProps) {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <div data-testid="lineage-diff-loading" role="status" aria-live="polite">
        {t('lineage.diff.loading', 'Loading lineage diff…')}
      </div>
    );
  }
  if (error) {
    return (
      <div
        data-testid="lineage-diff-error"
        role="alert"
        className={styles.error}
      >
        {t('lineage.diff.error', 'Failed to load diff:')} {error.message}
      </div>
    );
  }
  if (!diff) {
    return (
      <div data-testid="lineage-diff-empty">
        {t('lineage.diff.no_anchor', 'Pick two anchors to compute a diff.')}
      </div>
    );
  }

  const renderBucket = (
    bucket: keyof typeof BUCKET_STYLES,
    items: LineageDiffEdge[],
  ) => {
    const style = BUCKET_STYLES[bucket];
    return (
      <section
        key={bucket}
        data-testid={`${style.testid}-section`}
        aria-label={t(style.labelKey, style.fallback)}
        className={`${styles.bucket} ${style.className}`}
      >
        <h4 className={styles.bucketHeading}>
          <span aria-hidden="true" className={styles.glyph}>
            {style.glyph}
          </span>
          {t(style.labelKey, style.fallback)} ({items.length})
        </h4>
        {items.length === 0 ? (
          <p className={styles.bucketEmpty}>
            {t('lineage.diff.empty_bucket', '— no edges in this bucket —')}
          </p>
        ) : (
          <ul className={styles.bucketList}>
            {items.map((edge, i) => (
              <li
                key={`${bucket}-${edge.id ?? i}`}
                data-testid={`${style.testid}-row`}
              >
                {formatEdgeLabel(edge)}
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  };

  return (
    <div data-testid="lineage-diff-view">
      <header className={styles.header}>
        <h3 className={styles.heading}>
          {t('lineage.diff.heading', 'Lineage diff')}
        </h3>
        <small data-testid="lineage-diff-anchors">
          {t('lineage.diff.from', 'from')} <code>{diff.from.timestamp}</code>{' '}
          ({diff.from.source}) {' → '}
          {t('lineage.diff.to', 'to')} <code>{diff.to.timestamp}</code>{' '}
          ({diff.to.source})
        </small>
        <p data-testid="lineage-diff-summary" className={styles.summary}>
          {t('lineage.diff.summary', 'Summary:')}{' '}
          <strong>+{diff.summary.added}</strong>{' '}
          <strong>−{diff.summary.removed}</strong>{' '}
          <strong>={diff.summary.unchanged}</strong>
          {/* `modified` is always 0 per REQ-LIN-F5-002 but we render
              it for transparency — operators can verify the SCD-2
              close-and-reopen invariant from the UI. */}
          {' '}<small>(modified: {diff.summary.modified ?? 0})</small>
        </p>
      </header>

      {renderBucket('added', diff.added)}
      {renderBucket('removed', diff.removed)}
      {renderBucket('unchanged', diff.unchanged)}
    </div>
  );
}

export default LineageDiffView;
