/**
 * 285.9.4.1 — WizardDirectionPicker sub-component.
 *
 * Lets the user choose between code-first and contract-first flow.
 */
import React from 'react';

interface Props {
  current: 'code-first' | 'contract-first' | null;
  onSelect: (direction: 'code-first' | 'contract-first') => void;
}

export function WizardDirectionPicker({ current, onSelect }: Props): React.ReactElement {
  return (
    <div className="wizard-direction-picker">
      <h2>Choose Your Direction</h2>
      <div className="direction-cards">
        <button
          className={`direction-card ${current === 'code-first' ? 'selected' : ''}`}
          onClick={() => onSelect('code-first')}
          aria-pressed={current === 'code-first'}
        >
          <h3>Code First</h3>
          <p>
            Import an existing dbt project. Meshan&apos;t will generate a
            HubContract from your models.
          </p>
        </button>
        <button
          className={`direction-card ${current === 'contract-first' ? 'selected' : ''}`}
          onClick={() => onSelect('contract-first')}
          aria-pressed={current === 'contract-first'}
        >
          <h3>Contract First</h3>
          <p>
            Start from a HubContract. Meshan&apos;t will scaffold dbt model
            files for you.
          </p>
        </button>
      </div>
    </div>
  );
}
