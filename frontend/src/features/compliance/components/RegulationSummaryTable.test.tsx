import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RegulationSummaryTable } from './RegulationSummaryTable';

describe('RegulationSummaryTable', () => {
  it('renders nothing for null rows', () => {
    const { container } = render(<RegulationSummaryTable rows={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when rows is not an array (defensive)', () => {
    const { container } = render(
      <RegulationSummaryTable rows={{ not_an: 'array' } as unknown} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing for empty array', () => {
    const { container } = render(<RegulationSummaryTable rows={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders rows and maps extra primitive columns', () => {
    render(
      <RegulationSummaryTable
        rows={[
          { regulation: 'GDPR', status: 'PASS', violations: 0, triggered_by: 'EMAIL' },
          { regulation: 'HIPAA', status: 'WARN', violations: 2 },
        ]}
      />
    );
    expect(screen.getByTestId('regulation-summary-table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'triggered_by' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'EMAIL' })).toBeInTheDocument();
  });

  it('skips rows without a regulation string', () => {
    render(
      <RegulationSummaryTable
        rows={[{ status: 'PASS' }, { regulation: 'GDPR', status: 'OK' }] as unknown}
      />
    );
    expect(screen.getByRole('cell', { name: 'GDPR' })).toBeInTheDocument();
    expect(screen.queryByRole('cell', { name: 'PASS' })).not.toBeInTheDocument();
  });
});
