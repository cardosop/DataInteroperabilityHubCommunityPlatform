/**
 * Phase 231.5 — Renders `ComplianceRunResults.cross_border_alert` from compliance v2.
 */

import type { ComplianceCrossBorderAlert } from '../../../shared/types/compliance';

function regulationKeys(alert: ComplianceCrossBorderAlert): string[] {
  const keys = alert.regulations ?? alert.applicable_regulations ?? [];
  return Array.isArray(keys) ? [...keys] : [];
}

export interface CrossBorderAlertCardProps {
  alert: ComplianceCrossBorderAlert | null | undefined;
}

export function CrossBorderAlertCard({ alert }: CrossBorderAlertCardProps) {
  if (alert == null) {
    return null;
  }

  const keys = regulationKeys(alert);
  const applicable = alert.applicable === true;
  const safeguards = alert.requires_safeguards === true;

  return (
    <section
      className={`phase19-alert-card phase19-cross-border ${applicable ? 'phase19-alert-triggered' : 'phase19-alert-clear'}`}
      data-testid="cross-border-alert-card"
      aria-label="Cross-border transfer alert"
    >
      <h3 className="phase19-alert-title">Cross-border transfer safeguards</h3>
      {alert.message != null && String(alert.message).trim() !== '' && (
        <p className="phase19-alert-message">{String(alert.message)}</p>
      )}
      <p className="phase19-alert-status">
        {applicable
          ? 'Applicable: selected regulations include cross-border transfer restrictions or safeguards.'
          : 'Not applicable for this run under the current regulation set.'}
      </p>
      {safeguards && applicable && (
        <p className="phase19-alert-hint">Safeguards or transfer mechanisms may be required before storage or export.</p>
      )}
      {keys.length > 0 && (
        <ul className="phase19-alert-reg-list" data-testid="cross-border-alert-regulations">
          {keys.sort().map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
