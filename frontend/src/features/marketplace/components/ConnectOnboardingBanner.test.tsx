/**
 * W5.4 (MEDIUM-8 + submit pending) — the Connect-onboarding CTA failure
 * was console-only (debugLogger) and the button had no in-flight guard.
 * Pins: a failed onboarding-link POST surfaces an assertive error toast,
 * and the CTA is disabled while the request is in flight.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../../shared/components/Toast';
import { ConnectOnboardingBanner } from './ConnectOnboardingBanner';

describe('ConnectOnboardingBanner', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('surfaces a failed onboarding-link request with an error toast', async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValue(new Error('network down'));

    render(
      <ToastProvider>
        <ConnectOnboardingBanner />
      </ToastProvider>,
    );

    await user.click(screen.getByRole('button', { name: /start onboarding/i }));

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
    });
  });

  it('surfaces a non-OK response with an error toast', async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'KYB already in progress' }),
    });

    render(
      <ToastProvider>
        <ConnectOnboardingBanner />
      </ToastProvider>,
    );

    await user.click(screen.getByRole('button', { name: /start onboarding/i }));

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/KYB already in progress/i);
    });
  });

  it('disables the CTA while the request is in flight', async () => {
    const user = userEvent.setup();
    let resolveFetch: (value: unknown) => void = () => {};
    fetchMock.mockImplementation(
      () => new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    render(
      <ToastProvider>
        <ConnectOnboardingBanner />
      </ToastProvider>,
    );

    const cta = screen.getByRole('button', { name: /start onboarding/i });
    await user.click(cta);

    expect(cta).toBeDisabled();

    resolveFetch({ ok: true, json: () => Promise.resolve({}) });
    await waitFor(() => expect(cta).not.toBeDisabled());
  });
});
