/**
 * Retention Policy Edit Page Tests
 * Real useRetentionPolicy and useUpdateRetentionPolicy; only API client mocked (no mocks of application code).
 * Scenarios: loading, error, form with data, submit, validation, mutation error.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RetentionPolicy } from '../../../shared/types/governanceRetention';
import { RetentionAction, RetentionPolicyType } from '../../../shared/types/governanceRetention';
import { RetentionPolicyEditPage } from './RetentionPolicyEditPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

const VALID_ASSET_UUID = '550e8400-e29b-41d4-a716-446655440000';

const mockPolicy: RetentionPolicy = {
  id: 'policy-1',
  tenant: 'tenant-1',
  name: 'Test Policy',
  description: 'Test description',
  asset: VALID_ASSET_UUID,
  dataset: null,
  file: null,
  policy_type: RetentionPolicyType.TIME_BASED,
  retention_period_days: 30,
  event_trigger: null,
  action: RetentionAction.SOFT_DELETE,
  grace_period_days: 30,
  legal_hold: false,
  legal_hold_reason: null,
  legal_hold_expires_at: null,
  enabled: true,
  last_enforced_at: null,
  created_by: 'user-1',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('RetentionPolicyEditPage', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/governance/retention/policy-1/edit']}>
          <Routes>
            <Route path="/governance/retention/:id/edit" element={children} />
            <Route
              path="/governance/retention/:id"
              element={<div data-testid="detail-placeholder">Detail</div>}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockClient = realClient;
    vi.mocked(mockClient.get).mockClear();
    vi.mocked(mockClient.patch).mockClear();
  });

  it('should display loading state', async () => {
    let resolveGet: (value: unknown) => void;
    const getPromise = new Promise((resolve) => {
      resolveGet = resolve;
    });
    vi.mocked(mockClient.get).mockReturnValue(getPromise as never);

    render(<RetentionPolicyEditPage />, { wrapper });

    expect(screen.getByText(/loading retention policy/i)).toBeInTheDocument();

    resolveGet!({ data: mockPolicy });
    await waitFor(() => {
      expect(screen.queryByText(/loading retention policy/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    const err = {
      response: {
        status: 404,
        data: {
          error: {
            code: 'NOT_FOUND',
            message: 'Policy not found',
            http_status: 404,
            request_id: 'req-1',
            timestamp: new Date().toISOString(),
          },
        },
      },
    };
    vi.mocked(mockClient.get).mockRejectedValue(err);

    render(<RetentionPolicyEditPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/failed to load retention policy/i)).toBeInTheDocument();
    });
  });

  it('should display form with policy data', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: mockPolicy,
    } as never);

    render(<RetentionPolicyEditPage />, { wrapper });

    await waitFor(() => {
      const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
      expect(nameInput.value).toBe('Test Policy');
    });

    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/policy type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/retention period/i)).toBeInTheDocument();
  });

  it('should validate required name on submit', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockResolvedValue({
      data: mockPolicy,
    } as never);

    render(<RetentionPolicyEditPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
    await user.clear(nameInput);

    const form = document.querySelector('form') as HTMLFormElement;
    expect(form).toBeTruthy();
    fireEvent.submit(form);

    await waitFor(
      () => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('should submit form with updated data', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockResolvedValue({
      data: mockPolicy,
    } as never);
    vi.mocked(mockClient.patch).mockResolvedValue({
      data: { ...mockPolicy, name: 'Updated Policy' },
    } as never);

    render(<RetentionPolicyEditPage />, { wrapper });

    await waitFor(() => {
      const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
      expect(nameInput.value).toBe('Test Policy');
    });

    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, 'Updated Policy');

    const submitButton = screen.getByRole('button', { name: /update retention policy/i });
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(mockClient.patch).toHaveBeenCalled();
        const patchUrl = vi.mocked(mockClient.patch).mock.calls[0][0];
        const patchBody = vi.mocked(mockClient.patch).mock.calls[0][1];
        expect(patchUrl).toContain('policy-1');
        expect(patchBody?.name).toBe('Updated Policy');
      },
      { timeout: 5000 }
    );
  });

  it('should display mutation error when update fails', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockResolvedValue({
      data: mockPolicy,
    } as never);
    vi.mocked(mockClient.patch).mockRejectedValue({
      response: {
        status: 400,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid data',
            http_status: 400,
            request_id: 'req-1',
            timestamp: new Date().toISOString(),
          },
        },
      },
    });

    render(<RetentionPolicyEditPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    const submitButton = screen.getByRole('button', { name: /update retention policy/i });
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });
});
