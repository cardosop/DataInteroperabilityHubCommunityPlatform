import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LocalisationAlertCard } from './LocalisationAlertCard';

describe('LocalisationAlertCard', () => {
  it('renders nothing when alert is undefined', () => {
    const { container } = render(<LocalisationAlertCard alert={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows triggered styling and regulations', () => {
    render(
      <LocalisationAlertCard
        alert={{
          applicable: true,
          regulations: ['PIPL_CN'],
          message: 'Store in CN region.',
        }}
      />
    );
    expect(screen.getByTestId('localisation-alert-card')).toHaveClass('phase19-alert-triggered');
    expect(screen.getByText('Store in CN region.')).toBeInTheDocument();
    expect(screen.getByTestId('localisation-alert-regulations').textContent).toContain(
      'PIPL_CN'
    );
  });
});
