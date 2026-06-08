/**
 * DatasetVersionDiffView — unit coverage without mocked HTTP (fixture props only).
 */

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DatasetVersionDiffView } from './DatasetVersionDiffView';

describe('DatasetVersionDiffView', () => {
  it('renders added vs modified buckets from API-shaped changes', () => {
    render(
      <DatasetVersionDiffView
        compatibilityLevel="BACKWARD_COMPATIBLE"
        summary={{ FIELD_ADDED: 1, FIELD_TYPE_CHANGED: 1 }}
        changes={[
          {
            type: 'FIELD_ADDED',
            field_name: 'email',
            description: "Field 'email' added",
            breaking: false,
            old_value: null,
            new_value: { name: 'email' },
          },
          {
            type: 'FIELD_TYPE_CHANGED',
            field_name: 'age',
            description: "Field 'age' type changed",
            breaking: true,
            old_value: 'integer',
            new_value: 'string',
          },
        ]}
        version1Label="Version 1"
        version2Label="Version 2"
      />
    );

    expect(screen.getByTestId('dataset-version-diff-view')).toBeInTheDocument();

    const added = screen.getByRole('region', { name: /Added fields/i });
    expect(within(added).getByRole('cell', { name: 'email' })).toBeInTheDocument();

    const modified = screen.getByRole('region', { name: /Modified fields/i });
    expect(within(modified).getByRole('cell', { name: 'age' })).toBeInTheDocument();
    expect(within(modified).getByText('Yes')).toBeInTheDocument();

    expect(screen.getByTestId('dataset-version-diff-summary')).toHaveTextContent('FIELD_ADDED');
  });

  it('renders removed fields in their bucket', () => {
    render(
      <DatasetVersionDiffView
        compatibilityLevel="FORWARD_COMPATIBLE"
        summary={{ FIELD_REMOVED: 1 }}
        changes={[
          {
            type: 'FIELD_REMOVED',
            field_name: 'legacy_id',
            description: "Field 'legacy_id' removed",
            breaking: true,
            old_value: { name: 'legacy_id' },
            new_value: null,
          },
        ]}
        version1Label="Version 1"
        version2Label="Version 2"
      />
    );

    const removed = screen.getByRole('region', { name: /Removed fields/i });
    expect(within(removed).getByRole('cell', { name: 'legacy_id' })).toBeInTheDocument();
    expect(within(removed).getByText('Yes')).toBeInTheDocument();
  });
});
