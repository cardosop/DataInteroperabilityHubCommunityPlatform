/**
 * PasswordResetConfirmPage tests — Phase 221.1
 *
 * Covers:
 *  - 221.1.2  Token is cleared from the URL after being read
 *  - 221.1.3  Token read from URL fragment (#token=…) instead of query string
 *  - Basic rendering and form behaviour
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { PasswordResetConfirmPage } from './PasswordResetConfirmPage';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function Wrapper({ children, initialEntries }: { children: ReactNode; initialEntries?: string[] }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries ?? ['/password-reset/confirm']}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/* ------------------------------------------------------------------ */
/*  Setup                                                              */
/* ------------------------------------------------------------------ */

let mock: HttpClient;
const replaceStateSpy = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  mock = apiClient.getClient();
  vi.mocked(mock.get).mockResolvedValue({
    data: { count: 0, results: [], page: 1, page_size: 20, total_pages: 0, has_next: false, has_previous: false },
  });

  // Spy on history.replaceState so we can assert the URL is cleaned.
  replaceStateSpy.mockReset();
  vi.spyOn(window.history, 'replaceState').mockImplementation(replaceStateSpy);
});

describe('PasswordResetConfirmPage', () => {
  /* ---------------------------------------------------------------- */
  /*  Basic rendering                                                  */
  /* ---------------------------------------------------------------- */
  it('renders the form with token and password fields', () => {
    render(<PasswordResetConfirmPage />, {
      wrapper: ({ children }) => <Wrapper>{children}</Wrapper>,
    });

    expect(screen.getByLabelText(/reset token/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/new password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  221.1.2 — Token cleared from URL after being read                */
  /* ---------------------------------------------------------------- */
  describe('token URL cleanup (221.1.2)', () => {
    it('clears the token from the URL via history.replaceState when token is in query string', async () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm?token=secret-reset-token']}>
            {children}
          </Wrapper>
        ),
      });

      // The token field should be populated
      await waitFor(() => {
        expect(screen.getByLabelText(/reset token/i)).toHaveValue('secret-reset-token');
      });

      // history.replaceState must have been called to strip the token
      expect(replaceStateSpy).toHaveBeenCalled();
      const [, , newUrl] = replaceStateSpy.mock.calls[0];
      // The cleaned URL must NOT contain the token value
      expect(newUrl).not.toContain('secret-reset-token');
      expect(newUrl).not.toContain('token=');
    });

    it('clears the token from the URL when token is in the hash fragment', async () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm#token=fragment-token']}>
            {children}
          </Wrapper>
        ),
      });

      await waitFor(() => {
        expect(screen.getByLabelText(/reset token/i)).toHaveValue('fragment-token');
      });

      expect(replaceStateSpy).toHaveBeenCalled();
      const [, , newUrl] = replaceStateSpy.mock.calls[0];
      expect(newUrl).not.toContain('fragment-token');
      expect(newUrl).not.toContain('token=');
    });

    it('does NOT call replaceState when there is no token in the URL', () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm']}>
            {children}
          </Wrapper>
        ),
      });

      // No token → no URL cleanup needed
      expect(replaceStateSpy).not.toHaveBeenCalled();
    });
  });

  /* ---------------------------------------------------------------- */
  /*  221.1.3 — Fragment-based token extraction                        */
  /* ---------------------------------------------------------------- */
  describe('fragment-based token support (221.1.3)', () => {
    it('extracts token from hash fragment (#token=…)', async () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm#token=hash-based-token']}>
            {children}
          </Wrapper>
        ),
      });

      await waitFor(() => {
        expect(screen.getByLabelText(/reset token/i)).toHaveValue('hash-based-token');
      });
    });

    it('prefers hash fragment token over query string token', async () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm?token=query-token#token=fragment-token']}>
            {children}
          </Wrapper>
        ),
      });

      await waitFor(() => {
        // Fragment should take priority (never sent to server)
        expect(screen.getByLabelText(/reset token/i)).toHaveValue('fragment-token');
      });
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Form submission                                                  */
  /* ---------------------------------------------------------------- */
  describe('form submission', () => {
    it('submits the token and new password via POST', async () => {
      vi.mocked(mock.post).mockResolvedValueOnce({
        data: { message: 'Password reset successfully.' },
      });

      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm#token=submit-token']}>
            {children}
          </Wrapper>
        ),
      });

      await waitFor(() => {
        expect(screen.getByLabelText(/reset token/i)).toHaveValue('submit-token');
      });

      fireEvent.change(screen.getByLabelText(/new password/i), {
        target: { value: 'NewSecure123!' },
      });
      fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

      await waitFor(() => {
        expect(screen.getByText(/password reset successfully/i)).toBeInTheDocument();
      });

      expect(mock.post).toHaveBeenCalledWith(
        '/auth/password-reset/confirm/',
        { token: 'submit-token', new_password: 'NewSecure123!' },
      );
    });

    it('shows error when token is missing and form is submitted', async () => {
      render(<PasswordResetConfirmPage />, {
        wrapper: ({ children }) => (
          <Wrapper initialEntries={['/password-reset/confirm']}>
            {children}
          </Wrapper>
        ),
      });

      // Password field needs a value to pass HTML validation in tests
      fireEvent.change(screen.getByLabelText(/new password/i), {
        target: { value: 'SomePass123!' },
      });

      // Try submitting the form directly
      fireEvent.submit(screen.getByRole('button', { name: /reset password/i }).closest('form')!);

      await waitFor(() => {
        expect(screen.getByText(/missing reset token/i)).toBeInTheDocument();
      });
    });
  });
});
