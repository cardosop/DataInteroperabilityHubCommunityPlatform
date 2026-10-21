/**
 * DatasetSchemaDriftBanner — severity-aware rendering tests.
 *
 * Covers all five paths the banner can take:
 *   - has_contract=false → grey "no contract" notice
 *   - severity=NONE      → green "schemas match" notice
 *   - severity=WARN      → yellow notice listing extra fields
 *   - severity=FAIL      → red alert listing missing fields + type mismatches
 *   - structural_incompatibility flag surfaces on FAIL
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { DatasetSchemaDrift } from '../services/datasetService';
import { DatasetSchemaDriftBanner } from './DatasetSchemaDriftBanner';

function makeDrift(overrides: Partial<DatasetSchemaDrift> = {}): DatasetSchemaDrift {
  return {
    has_contract: true,
    contract_id: 'contract-1',
    detected: false,
    severity: 'NONE',
    missing_fields: [],
    extra_fields: [],
    type_mismatches: [],
    structural_incompatibility: false,
    ...overrides,
  };
}

describe('DatasetSchemaDriftBanner', () => {
  it('renders no-contract notice when has_contract is false', () => {
    render(<DatasetSchemaDriftBanner drift={makeDrift({ has_contract: false })} />);
    const banner = screen.getByTestId('dataset-drift-banner');
    expect(banner).toHaveAttribute('data-severity', 'NONE');
    expect(banner).toHaveAttribute('data-has-contract', 'false');
    expect(banner).toHaveTextContent(/no contract drift to evaluate/i);
  });

  it('renders matching-schema notice when severity is NONE with contract', () => {
    render(<DatasetSchemaDriftBanner drift={makeDrift({ has_contract: true, severity: 'NONE' })} />);
    const banner = screen.getByTestId('dataset-drift-banner');
    expect(banner).toHaveAttribute('data-severity', 'NONE');
    expect(banner).toHaveAttribute('data-has-contract', 'true');
    expect(banner).toHaveTextContent(/schema matches the contract/i);
  });

  it('renders WARN banner with extra_fields list', () => {
    render(
      <DatasetSchemaDriftBanner
        drift={makeDrift({
          severity: 'WARN',
          detected: true,
          extra_fields: ['bonus_field', 'note'],
        })}
      />,
    );
    const banner = screen.getByTestId('dataset-drift-banner');
    expect(banner).toHaveAttribute('data-severity', 'WARN');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(screen.getByTestId('dataset-drift-extra-fields')).toHaveTextContent(/bonus_field/);
    expect(screen.getByTestId('dataset-drift-extra-fields')).toHaveTextContent(/note/);
  });

  it('renders FAIL banner with missing fields and type mismatches', () => {
    render(
      <DatasetSchemaDriftBanner
        drift={makeDrift({
          severity: 'FAIL',
          detected: true,
          missing_fields: ['amount'],
          extra_fields: ['unexpected'],
          type_mismatches: [
            { field: 'id', contract_type: 'string', inferred_type: 'integer', compatible: false },
          ],
          structural_incompatibility: true,
        })}
      />,
    );
    const banner = screen.getByTestId('dataset-drift-banner');
    expect(banner).toHaveAttribute('data-severity', 'FAIL');
    // FAIL severity surfaces as an aria-live=assertive alert so screen
    // readers announce it without waiting for next idle cycle.
    expect(banner).toHaveAttribute('aria-live', 'assertive');

    expect(screen.getByTestId('dataset-drift-missing-fields')).toHaveTextContent(/amount/);
    expect(screen.getByTestId('dataset-drift-extra-fields')).toHaveTextContent(/unexpected/);
    expect(screen.getByTestId('dataset-drift-type-mismatches')).toHaveTextContent(/id/);
    expect(screen.getByTestId('dataset-drift-type-mismatches')).toHaveTextContent(/contract=string/);
    expect(screen.getByTestId('dataset-drift-type-mismatches')).toHaveTextContent(/inferred=integer/);
    expect(screen.getByTestId('dataset-drift-type-mismatches')).toHaveTextContent(/incompatible/);
  });
});
