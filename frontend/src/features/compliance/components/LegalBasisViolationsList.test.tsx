import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LegalBasisViolationsList } from './LegalBasisViolationsList';

describe('LegalBasisViolationsList', () => {
  it('renders nothing when list empty', () => {
    const { container } = render(<LegalBasisViolationsList violations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('lists regulation, basis, and violation text', () => {
    render(
      <LegalBasisViolationsList
        violations={[
          { regulation: 'GDPR', basis: 'CONSENT', violation: 'no_consent_obtained' },
        ]}
      />
    );
    expect(screen.getByTestId('legal-basis-violations-list')).toBeInTheDocument();
    expect(screen.getByText('GDPR')).toBeInTheDocument();
    expect(screen.getByText(/Basis: CONSENT/)).toBeInTheDocument();
    expect(screen.getByText('no_consent_obtained')).toBeInTheDocument();
  });
});
