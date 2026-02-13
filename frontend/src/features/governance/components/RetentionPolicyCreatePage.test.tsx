/**
 * Retention Policy Create Page Tests
 * Real useCreateRetentionPolicy; only axios mocked (no mocks of application code).
 * Scenarios: form render, validation (name, resource, retention period), submit success, mutation error, loading.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RetentionAction, RetentionPolicyType } from '../../../shared/types/governanceRetention';
import { RetentionPolicyCreatePage } from './RetentionPolicyCreatePage';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

import { apiClient } from '../../../shared/api/client';

describe('RetentionPolicyCreatePage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
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
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.post).mockClear();
  });

  it('should render form fields', () => {
    render(<RetentionPolicyCreatePage />, { wrapper });

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/asset id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/policy type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/retention period/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/action/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/enabled/i)).toBeInTheDocument();
  });

  it('should validate required name field', async () => {
    const user = userEvent.setup();

    render(<RetentionPolicyCreatePage />, { wrapper });

    const assetIdInput = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetIdInput, 'asset-1');

    const retentionPeriodInput = screen.getByLabelText(/retention period/i);
    await user.type(retentionPeriodInput, '30');

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

  it('should validate at least one resource ID', async () => {
    const user = userEvent.setup();

    render(<RetentionPolicyCreatePage />, { wrapper });

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'Test Policy');

    const retentionPeriodInput = screen.getByLabelText(/retention period/i);
    await user.type(retentionPeriodInput, '30');

    const form = document.querySelector('form') as HTMLFormElement;
    expect(form).toBeTruthy();
    fireEvent.submit(form);

    await waitFor(
      () => {
        expect(
          screen.getByText(/at least one of asset id, dataset id, or file id is required/i)
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('should validate retention period for time-based policies', async () => {
    const user = userEvent.setup();

    render(<RetentionPolicyCreatePage />, { wrapper });

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'Test Policy');

    const assetIdInput = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetIdInput, 'asset-1');

    const policyTypeSelect = screen.getByLabelText(/policy type/i);
    expect(policyTypeSelect).toHaveValue(RetentionPolicyType.TIME_BASED);

    const retentionPeriodInput = screen.getByLabelText(/retention period/i) as HTMLInputElement;
    await user.clear(retentionPeriodInput);
    expect(retentionPeriodInput.value).toBe('');

    const form = document.querySelector('form') as HTMLFormElement;
    expect(form).toBeTruthy();
    fireEvent.submit(form);

    await waitFor(
      () => {
        expect(
          screen.getByText(/retention period days is required for time-based policies/i)
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('should submit form with valid data', async () => {
    const user = userEvent.setup();
    const createdPolicy = {
      id: 'policy-1',
      name: 'Test Policy',
      tenant: 'tenant-1',
      description: 'Test description',
      asset: 'asset-1',
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
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: createdPolicy,
    } as any);

    render(<RetentionPolicyCreatePage />, { wrapper });

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'Test Policy');

    const descriptionInput = screen.getByLabelText(/description/i);
    await user.type(descriptionInput, 'Test description');

    const assetIdInput = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetIdInput, 'asset-1');

    const retentionPeriodInput = screen.getByLabelText(/retention period/i);
    await user.clear(retentionPeriodInput);
    await user.type(retentionPeriodInput, '30');

    const submitButton = screen.getByRole('button', { name: /create retention policy/i });
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(mockAxiosInstance.post).toHaveBeenCalledWith(
          'governance/retention-policies/',
          expect.objectContaining({
            name: 'Test Policy',
            description: 'Test description',
            asset_id: 'asset-1',
            policy_type: RetentionPolicyType.TIME_BASED,
            retention_period_days: 30,
            action: RetentionAction.SOFT_DELETE,
            enabled: true,
          })
        );
      },
      { timeout: 5000 }
    );
  });

  it('should display mutation error when create fails', async () => {
    const user = userEvent.setup();
    vi.mocked(mockAxiosInstance.post).mockRejectedValue({
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

    render(<RetentionPolicyCreatePage />, { wrapper });

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'Test Policy');

    const assetIdInput = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetIdInput, 'asset-1');

    const retentionPeriodInput = screen.getByLabelText(/retention period/i);
    await user.clear(retentionPeriodInput);
    await user.type(retentionPeriodInput, '30');

    const submitButton = screen.getByRole('button', { name: /create retention policy/i });
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });

  it('should show loading state during submission', async () => {
    const user = userEvent.setup();
    let resolvePost: (value: unknown) => void;
    const postPromise = new Promise((resolve) => {
      resolvePost = resolve;
    });
    vi.mocked(mockAxiosInstance.post).mockReturnValue(postPromise as any);

    render(<RetentionPolicyCreatePage />, { wrapper });

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'Test Policy');

    const assetIdInput = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetIdInput, 'asset-1');

    const retentionPeriodInput = screen.getByLabelText(/retention period/i);
    await user.clear(retentionPeriodInput);
    await user.type(retentionPeriodInput, '30');

    const submitButton = screen.getByRole('button', { name: /create retention policy/i });
    await user.click(submitButton);

    expect(screen.getByRole('button', { name: /creating/i })).toBeInTheDocument();

    resolvePost!({
      data: {
        id: 'policy-1',
        name: 'Test Policy',
        tenant: 'tenant-1',
        description: '',
        asset: 'asset-1',
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
      },
    });
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /creating/i })).not.toBeInTheDocument();
    });
  });
});
