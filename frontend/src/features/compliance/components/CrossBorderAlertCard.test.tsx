import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CrossBorderAlertCard } from './CrossBorderAlertCard';

describe('CrossBorderAlertCard', () => {
  it('renders nothing when alert is null', () => {
    const { container } = render(<CrossBorderAlertCard alert={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('lists regulations and highlights triggered applicable state', () => {
    render(
      <CrossBorderAlertCard
        alert={{
          applicable: true,
          regulations: ['LGPD', 'GDPR'],
          requires_safeguards: true,
          message: 'Use SCCs.',
        }}
      />
    );
    expect(screen.getByTestId('cross-border-alert-card')).toBeInTheDocument();
    expect(screen.getByTestId('cross-border-alert-card')).toHaveClass('phase19-alert-triggered');
    expect(screen.getByText('Use SCCs.')).toBeInTheDocument();
    const list = screen.getByTestId('cross-border-alert-regulations');
    expect(list.textContent).toContain('GDPR');
    expect(list.textContent).toContain('LGPD');
  });

  it('accepts legacy applicable_regulations key', () => {
    render(
      <CrossBorderAlertCard
        alert={{ applicable: true, applicable_regulations: ['PIPL_CN'] }}
      />
    );
    expect(screen.getByTestId('cross-border-alert-regulations').textContent).toContain(
      'PIPL_CN'
    );
  });

  it('renders clear state when not applicable', () => {
    render(<CrossBorderAlertCard alert={{ applicable: false }} />);
    expect(screen.getByTestId('cross-border-alert-card')).toHaveClass('phase19-alert-clear');
    expect(screen.getByText(/Not applicable/)).toBeInTheDocument();
  });
});
