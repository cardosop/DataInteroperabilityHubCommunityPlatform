/**
 * Phase 85.6 — FullPageSpinner tests.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

// Mock LoadingSpinner since FullPageSpinner delegates to it
vi.mock('../LoadingSpinner', () => ({
  LoadingSpinner: ({ message }: { message?: string }) => (
    <div data-testid="loading-spinner">{message ?? 'Loading...'}</div>
  ),
}));

import { FullPageSpinner } from '../FullPageSpinner';

describe('FullPageSpinner', () => {
  it('renders without crashing', () => {
    const { container } = render(<FullPageSpinner />);
    expect(container.firstChild).toBeTruthy();
  });

  it('is centered with full viewport height', () => {
    const { container } = render(<FullPageSpinner />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.minHeight).toBe('100vh');
    expect(wrapper.style.justifyContent).toBe('center');
    expect(wrapper.style.alignItems).toBe('center');
  });

  it('passes message to LoadingSpinner', () => {
    render(<FullPageSpinner message="Please wait" />);
    expect(screen.getByText('Please wait')).toBeTruthy();
  });
});
