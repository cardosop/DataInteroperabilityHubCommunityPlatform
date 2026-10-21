/**
 * Phase 250.7.A.3 TDD pin for `<SemanticDegradedBanner>`.
 *
 * Pure presentational component — no React Query / no providers
 * needed. Pins the wire contract:
 *
 *  * Returns null for UNKNOWN / PASS / WARN / null / undefined
 *    (banner only fires on FAIL — the load-bearing positive case).
 *  * Renders the structured banner for FAIL with role="alert" +
 *    aria-live="polite" + data-testid.
 *  * "Retry mapping" CTA is disabled when no onRetry handler is
 *    supplied (UX clarity — operator sees the action exists).
 *  * onRetry click handler is wired through.
 *  * isRetrying disables the button and changes the label.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SemanticDegradedBanner } from './SemanticDegradedBanner';

describe('SemanticDegradedBanner', () => {
  it.each(['UNKNOWN', 'PASS', 'WARN', null, undefined] as const)(
    'returns null for non-FAIL status: %s',
    (status) => {
      const { container } = render(
        <SemanticDegradedBanner semanticStatus={status as never} />,
      );
      expect(container.firstChild).toBeNull();
    },
  );

  it('renders the banner for FAIL with the right a11y attributes', () => {
    render(<SemanticDegradedBanner semanticStatus="FAIL" />);
    const banner = screen.getByTestId('semantic-degraded-banner');
    expect(banner).toBeInTheDocument();
    expect(banner.getAttribute('role')).toBe('alert');
    expect(banner.getAttribute('aria-live')).toBe('polite');
    expect(banner.getAttribute('aria-label')).toBeTruthy();
    expect(banner.getAttribute('data-semantic-status')).toBe('FAIL');
    // Heading + body copy match the spec's UX-writer brief
    // ("active but not yet discoverable"…).
    expect(
      screen.getByText(/active, but not yet discoverable/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not yet discoverable in semantic search/i),
    ).toBeInTheDocument();
  });

  it('renders the Retry mapping CTA disabled when no onRetry handler', () => {
    render(<SemanticDegradedBanner semanticStatus="FAIL" />);
    const button = screen.getByTestId('semantic-degraded-banner-retry');
    expect(button).toBeDisabled();
    expect(button.getAttribute('title')).toMatch(/not available/i);
  });

  it('wires the onRetry click handler when supplied', () => {
    const handleRetry = vi.fn();
    render(
      <SemanticDegradedBanner
        semanticStatus="FAIL"
        onRetry={handleRetry}
      />,
    );
    const button = screen.getByTestId('semantic-degraded-banner-retry');
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('disables the button + flips label while isRetrying', () => {
    const handleRetry = vi.fn();
    render(
      <SemanticDegradedBanner
        semanticStatus="FAIL"
        onRetry={handleRetry}
        isRetrying={true}
      />,
    );
    const button = screen.getByTestId('semantic-degraded-banner-retry');
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/Retrying/i);
  });
});
