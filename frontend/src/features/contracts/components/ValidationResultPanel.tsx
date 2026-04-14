/**
 * ValidationResultPanel — shows draft validation results inline below
 * the contract editor on the create page (Phase 219.5).
 *
 * States: loading · valid · warnings · errors
 * Accessibility: role="alert" for errors, role="status" for success/warnings.
 */

import { useState } from 'react';
import type { DraftValidationResult } from '../../../shared/types/contracts';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import './ValidationResultPanel.css';

interface Props {
  result: DraftValidationResult | null;
  isLoading: boolean;
}

export function ValidationResultPanel({ result, isLoading }: Props) {
  const [warningsExpanded, setWarningsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="validation-result-panel validation-result-panel--loading" role="status">
        <LoadingSpinner message="Validating..." />
      </div>
    );
  }

  if (!result) return null;

  if (!result.valid) {
    return (
      <div className="validation-result-panel validation-result-panel--error" role="alert">
        <div className="validation-result-panel__header">
          <span className="validation-result-panel__icon">&#10060;</span>
          <strong>Validation failed</strong>
          {result.detected_spec_type !== 'UNKNOWN' && (
            <span className="validation-result-panel__spec">
              {result.detected_spec_type} {result.detected_spec_version}
            </span>
          )}
        </div>
        {result.normalization_errors.length > 0 && (
          <ul className="validation-result-panel__errors">
            {result.normalization_errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  const hasWarnings = result.normalization_warnings.length > 0;

  if (hasWarnings) {
    return (
      <div className="validation-result-panel validation-result-panel--warning" role="status" aria-live="polite">
        <div className="validation-result-panel__header">
          <span className="validation-result-panel__icon">&#9888;&#65039;</span>
          <strong>Valid with warnings</strong>
          <span className="validation-result-panel__spec">
            {result.detected_spec_type} {result.detected_spec_version}
          </span>
          <button
            type="button"
            className="validation-result-panel__toggle"
            onClick={() => setWarningsExpanded((v) => !v)}
            aria-expanded={warningsExpanded}
          >
            {warningsExpanded ? 'Hide' : 'Show'} {result.normalization_warnings.length} warning{result.normalization_warnings.length !== 1 ? 's' : ''}
          </button>
        </div>
        {warningsExpanded && (
          <ul className="validation-result-panel__warnings">
            {result.normalization_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="validation-result-panel validation-result-panel--success" role="status" aria-live="polite">
      <div className="validation-result-panel__header">
        <span className="validation-result-panel__icon">&#9989;</span>
        <strong>
          Valid {result.detected_spec_type} {result.detected_spec_version} — ready to create
        </strong>
      </div>
    </div>
  );
}
