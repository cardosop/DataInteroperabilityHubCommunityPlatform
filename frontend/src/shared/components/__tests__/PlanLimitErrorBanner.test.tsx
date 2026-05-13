/**
 * Phase 277.B.108 — PlanLimitErrorBanner tests.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { PlanLimitErrorBanner } from '../PlanLimitErrorBanner';

function renderWithRouter(props: Parameters<typeof PlanLimitErrorBanner>[0]) {
  return render(
    <MemoryRouter>
      <PlanLimitErrorBanner {...props} />
    </MemoryRouter>,
  );
}

describe('PlanLimitErrorBanner', () => {
  it('renders current and max values', () => {
    renderWithRouter({
      resourceLabel: 'assets',
      current: 95,
      max: 100,
    });
    expect(screen.getByText(/95.*100/)).toBeDefined();
    expect(screen.getByText(/assets/)).toBeDefined();
  });

  it('applies warning severity at >=80%', () => {
    renderWithRouter({ resourceLabel: 'datasets', current: 80, max: 100 });
    const banner = screen.getByTestId('plan-limit-error-banner');
    expect(banner.className).toContain('plan-limit-banner--warning');
  });

  it('applies critical severity at 100%', () => {
    renderWithRouter({ resourceLabel: 'webhooks', current: 100, max: 100 });
    const banner = screen.getByTestId('plan-limit-error-banner');
    expect(banner.className).toContain('plan-limit-banner--critical');
  });

  it('applies critical severity when current > max', () => {
    renderWithRouter({ resourceLabel: 'listings', current: 110, max: 100 });
    const banner = screen.getByTestId('plan-limit-error-banner');
    expect(banner.className).toContain('plan-limit-banner--critical');
  });

  it('shows plan tier when provided', () => {
    renderWithRouter({
      resourceLabel: 'contracts',
      current: 45,
      max: 50,
      planTier: 'Free',
    });
    expect(screen.getByText(/Free plan/)).toBeDefined();
  });

  it('has Upgrade Plan link', () => {
    renderWithRouter({ resourceLabel: 'models', current: 8, max: 10 });
    const link = screen.getByText('Upgrade Plan');
    expect(link.getAttribute('href')).toBe('/settings/billing');
  });

  it('has aria-live=polite for screen readers', () => {
    renderWithRouter({ resourceLabel: 'exports', current: 90, max: 100 });
    const banner = screen.getByRole('alert');
    expect(banner.getAttribute('aria-live')).toBe('polite');
  });

  it('renders detail message when provided', () => {
    renderWithRouter({
      resourceLabel: 'ingestions',
      current: 19,
      max: 20,
      detail: 'Remove unused scheduled ingestions or upgrade your plan.',
    });
    expect(screen.getByText(/Remove unused/)).toBeDefined();
  });

  it('allows custom testId', () => {
    renderWithRouter({
      resourceLabel: 'storage',
      current: 900,
      max: 1024,
      'data-testid': 'custom-banner',
    });
    expect(screen.getByTestId('custom-banner')).toBeDefined();
  });
});
