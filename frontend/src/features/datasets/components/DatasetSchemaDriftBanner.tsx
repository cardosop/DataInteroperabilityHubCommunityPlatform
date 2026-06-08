/**
 * Phase 260.4.D — schema-drift banner shown after a refresh-from-file
 * succeeds. Severity-aware:
 *
 *   - NONE + has_contract=true   → green "schemas match" notice.
 *   - NONE + has_contract=false  → grey "no contract attached" notice.
 *   - WARN                       → yellow notice listing extra fields.
 *   - FAIL                       → red alert listing missing fields +
 *                                  type mismatches; the structural
 *                                  incompatibility flag is rendered
 *                                  prominently so operators don't miss it.
 *
 * Pure presentational: takes a drift dict, renders the right surface.
 * Polling / mutation lives in the parent.
 */

import type { JSX } from 'react';

import type { DatasetSchemaDrift } from '../services/datasetService';
import './DatasetSchemaDriftBanner.css';

export interface DatasetSchemaDriftBannerProps {
  drift: DatasetSchemaDrift;
  className?: string;
}

export function DatasetSchemaDriftBanner({
  drift,
  className,
}: DatasetSchemaDriftBannerProps): JSX.Element | null {
  // No contract → grey informational notice; useful so the user knows
  // a clean drift response means "no contract to compare against",
  // not "schema matches".
  if (!drift.has_contract) {
    return (
      <section
        className={`dataset-drift-banner dataset-drift-banner-info ${className ?? ''}`.trim()}
        data-testid="dataset-drift-banner"
        data-severity="NONE"
        data-has-contract="false"
        role="status"
        aria-live="polite"
      >
        <strong>No contract drift to evaluate.</strong>{' '}
        <span>
          The asset has no active contract attached, so the new dataset version
          was accepted without schema-vs-contract comparison.
        </span>
      </section>
    );
  }

  if (drift.severity === 'NONE') {
    return (
      <section
        className={`dataset-drift-banner dataset-drift-banner-clean ${className ?? ''}`.trim()}
        data-testid="dataset-drift-banner"
        data-severity="NONE"
        data-has-contract="true"
        role="status"
        aria-live="polite"
      >
        <strong>Schema matches the contract.</strong>{' '}
        <span>The new dataset version conforms to the asset's active contract.</span>
      </section>
    );
  }

  if (drift.severity === 'WARN') {
    return (
      <section
        className={`dataset-drift-banner dataset-drift-banner-warn ${className ?? ''}`.trim()}
        data-testid="dataset-drift-banner"
        data-severity="WARN"
        role="alert"
        aria-live="polite"
      >
        <strong>Schema drift detected (compatible).</strong>{' '}
        <span>
          The new dataset version adds fields the contract doesn't declare. This is
          backward-compatible — readers expecting only contract fields keep working — but
          consumers of the new fields need a contract update to publish them.
        </span>
        {drift.extra_fields.length > 0 && (
          <div className="dataset-drift-section" data-testid="dataset-drift-extra-fields">
            <strong>Extra fields:</strong> {drift.extra_fields.join(', ')}
          </div>
        )}
      </section>
    );
  }

  // FAIL — structural incompatibility. Surface every category we have.
  return (
    <section
      className={`dataset-drift-banner dataset-drift-banner-fail ${className ?? ''}`.trim()}
      data-testid="dataset-drift-banner"
      data-severity="FAIL"
      role="alert"
      aria-live="assertive"
    >
      <strong>Schema drift detected (incompatible).</strong>{' '}
      <span>
        The new dataset version is structurally incompatible with the asset's active
        contract. Downstream consumers expecting the contract shape will fail.
      </span>
      {drift.missing_fields.length > 0 && (
        <div className="dataset-drift-section" data-testid="dataset-drift-missing-fields">
          <strong>Missing required fields:</strong> {drift.missing_fields.join(', ')}
        </div>
      )}
      {drift.extra_fields.length > 0 && (
        <div className="dataset-drift-section" data-testid="dataset-drift-extra-fields">
          <strong>Extra fields:</strong> {drift.extra_fields.join(', ')}
        </div>
      )}
      {drift.type_mismatches.length > 0 && (
        <div className="dataset-drift-section" data-testid="dataset-drift-type-mismatches">
          <strong>Type mismatches:</strong>
          <ul>
            {drift.type_mismatches.map((m) => (
              <li key={m.field}>
                <code>{m.field}</code>: contract={m.contract_type} vs inferred={m.inferred_type}
                {m.compatible === false ? ' (incompatible)' : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
