/**
 * Phase 231.5 — Renders `ComplianceRunResults.localisation_alert` (British field name on API).
 */

import type { ComplianceLocalisationAlert } from '../../../shared/types/compliance';

function regulationKeys(alert: ComplianceLocalisationAlert): string[] {
  const keys = alert.regulations ?? alert.applicable_regulations ?? [];
  return Array.isArray(keys) ? [...keys] : [];
}

export interface LocalisationAlertCardProps {
  alert: ComplianceLocalisationAlert | null | undefined;
}

export function LocalisationAlertCard({ alert }: LocalisationAlertCardProps) {
  if (alert == null) {
    return null;
  }

  const keys = regulationKeys(alert);
  const applicable = alert.applicable === true;

  return (
    <section
      className={`phase19-alert-card phase19-localisation ${applicable ? 'phase19-alert-triggered' : 'phase19-alert-clear'}`}
      data-testid="localisation-alert-card"
      aria-label="Data localisation alert"
    >
      <h3 className="phase19-alert-title">Data localisation</h3>
      {alert.message != null && String(alert.message).trim() !== '' && (
        <p className="phase19-alert-message">{String(alert.message)}</p>
      )}
      <p className="phase19-alert-status">
        {applicable
          ? 'Applicable: processing or storage may be restricted to specified jurisdictions.'
          : 'No additional localisation requirements flagged for this run.'}
      </p>
      {keys.length > 0 && (
        <ul className="phase19-alert-reg-list" data-testid="localisation-alert-regulations">
          {keys.sort().map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
