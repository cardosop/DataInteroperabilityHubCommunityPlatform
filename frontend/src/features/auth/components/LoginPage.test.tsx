/**
 * LoginPage component tests.
 * Real useAuthStore, useCapabilities, and authService; only axios mocked.
 * Scenarios: success (form submit, navigate), error (display message), a11y (labels/roles).
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginPage } from './LoginPage';

const mockAxiosInstance = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
})) as unknown as AxiosInstance;

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

import { apiClient } from '../../../shared/api/client';

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const client = apiClient.getClient();
    vi.mocked(client.get).mockClear();
    vi.mocked(client.post).mockClear();
  });

  it('should render login form with email and password fields', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: { paths: {} },
    });

    render(<LoginPage />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /data interoperability hub/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('should show error message on login failure', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: { paths: {} },
    });
    vi.mocked(mockAxiosInstance.post).mockRejectedValue(new Error('Invalid credentials'));

    const user = userEvent.setup();
    render(<LoginPage />, { wrapper });

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid credentials|login failed/i);
    });
  });

  it('should have accessible form controls', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: { paths: {} },
    });

    render(<LoginPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(emailInput).toHaveAttribute('aria-required', 'true');
    expect(passwordInput).toHaveAttribute('type', 'password');
    expect(passwordInput).toHaveAttribute('aria-required', 'true');
  });
});
