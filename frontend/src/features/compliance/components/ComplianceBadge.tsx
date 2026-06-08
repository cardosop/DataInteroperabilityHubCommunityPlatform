/**
 * Phase 231.3 / REQ-COMP-DISCO-001 — buyer-visible compliance discovery badge.
 * Parent routes should wrap this in ErrorBoundary so rendering failures do not blank the page.
 */

import { useState } from 'react';
import type { ComplianceRunSummary } from '../../../shared/types/complianceDiscovery';
import { Button } from '../../../shared/components/Button';
import {
  RISK_PILL_CLASS,
  copyTextToClipboard,
  riskDisplayLabel,
} from './complianceBadgeUtils';
import styles from './ComplianceBadge.module.css';

// ``RISK_PILL_CLASS`` / ``copyTextToClipboard`` / ``riskDisplayLabel``
// live in ``./complianceBadgeUtils`` so this file stays component-only
// (``react-refresh/only-export-components``).

function ComplianceRegulationSummaries({ summaries }: { summaries: unknown }) {
  if (summaries == null) return null;
  if (!Array.isArray(summaries)) {
    throw new Error('Compliance regulation summaries must be an array when provided');
  }
  if (summaries.length === 0) return null;
  return (
    <ul className={styles.summaries} aria-label="Regulation highlights">
      {summaries.slice(0, 5).map((item, idx) => (
        <li key={idx}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
      ))}
    </ul>
  );
}

export interface ComplianceBadgeProps {
  summary?: ComplianceRunSummary | null;
  /** Smaller layout for listing cards */
  compact?: boolean;
}

export function ComplianceBadge({ summary, compact = false }: ComplianceBadgeProps) {
  const [copyOk, setCopyOk] = useState<boolean | null>(null);

  if (!summary?.id) {
    return null;
  }

  const riskKey = (summary.risk_level ?? 'UNKNOWN').toString().trim().toUpperCase();
  const pillClass = RISK_PILL_CLASS[riskKey] ?? RISK_PILL_CLASS.UNKNOWN;
  const riskHuman = riskDisplayLabel(summary.risk_level);
  const ariaLabel = `${riskHuman} risk`;

  const lineParts = [
    `risk=${summary.risk_level ?? 'UNKNOWN'}`,
    summary.overall_status != null ? `overall=${summary.overall_status}` : null,
    summary.completed_at != null ? `completed_at=${summary.completed_at}` : null,
    `run_id=${summary.id}`,
  ].filter(Boolean);

  const handleCopy = async () => {
    const ok = await copyTextToClipboard(lineParts.join(' '));
    setCopyOk(ok);
    window.setTimeout(() => setCopyOk(null), 2500);
  };

  return (
    <div
      className={`${styles.wrap} ${compact ? styles.wrapCompact : ''}`}
      data-testid="compliance-discovery-badge"
    >
      <div className={styles.header}>
        <p className={styles.title}>Compliance</p>
        <span className={`${styles.pill} ${pillClass}`} aria-label={ariaLabel} role="status">
          {riskHuman}
        </span>
        {summary.overall_status ? (
          <span className={styles.meta} data-testid="compliance-badge-overall">
            Overall: {summary.overall_status}
            {summary.allowed_to_store != null
              ? ` · Storage: ${summary.allowed_to_store ? 'allowed' : 'not allowed'}`
              : ''}
          </span>
        ) : null}
      </div>
      <ComplianceRegulationSummaries summaries={summary.regulation_summaries} />
      <div className={styles.actions}>
        <Button
          type="button"
          variant="secondary"
          className={styles.copyBtn}
          data-testid="compliance-badge-copy"
          onClick={() => void handleCopy()}
        >
          Copy summary
        </Button>
        {copyOk === true ? (
          <span className={styles.meta} data-testid="compliance-badge-copy-ok">
            Copied
          </span>
        ) : null}
        {copyOk === false ? (
          <span className={styles.meta} role="alert">
            Copy failed
          </span>
        ) : null}
      </div>
    </div>
  );
}
