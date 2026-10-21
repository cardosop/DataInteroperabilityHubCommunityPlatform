/**
 * useAutoValidateContract tests — 222.5.
 *
 * Verifies the ref-guarded dry-run validation hook:
 *  - fires POST /contracts/validate-draft/ exactly once per contract ID
 *  - does NOT re-call on re-renders with the same contract
 *  - re-fires when the contract ID changes
 *  - surfaces valid / warning / invalid outcomes for banner consumers
 *  - does not fire when input is missing (`original_raw`)
 *
 * Real React Query + real hook; only the `apiClient` HTTP seam is auto-mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { StrictMode, type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import type { DraftValidationResult } from '../../../shared/types/contracts';
import { useAutoValidateContract } from './useAutoValidateContract';

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const validResult: DraftValidationResult = {
  valid: true,
  detected_spec_type: 'ODCS',
  detected_spec_version: '3.0.0',
  normalization_status: 'NORMALIZED_OK',
  normalization_errors: [],
  normalization_warnings: [],
};

const warnResult: DraftValidationResult = {
  ...validResult,
  normalization_status: 'NORMALIZED_WITH_WARNINGS',
  normalization_warnings: ['deprecated field used'],
};

const invalidResult: DraftValidationResult = {
  ...validResult,
  valid: false,
  normalization_status: 'NORMALIZATION_FAILED',
  normalization_errors: ['missing required property `id`'],
};

describe('useAutoValidateContract', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('does not fire when contract is null', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    renderHook(() => useAutoValidateContract(null), {
      wrapper: makeWrapper(queryClient),
    });
    await new Promise((r) => setTimeout(r, 10));
    expect(postMock).not.toHaveBeenCalled();
  });

  it('does not fire when original_raw is empty', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    renderHook(
      () =>
        useAutoValidateContract({
          id: 'c-1',
          original_raw: '',
          original_format: 'JSON',
        }),
      { wrapper: makeWrapper(queryClient) },
    );
    await new Promise((r) => setTimeout(r, 10));
    expect(postMock).not.toHaveBeenCalled();
  });

  it('calls validate-draft exactly once per contract id and surfaces valid=true', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    postMock.mockResolvedValue({ data: validResult } as never);

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) =>
        useAutoValidateContract({
          id,
          original_raw: '{"foo":"bar"}',
          original_format: 'JSON',
        }),
      {
        wrapper: makeWrapper(queryClient),
        initialProps: { id: 'c-1' },
      },
    );

    await waitFor(() => {
      expect(result.current.status).toBe('valid');
    });

    // Re-render with the SAME id — must not re-trigger.
    rerender({ id: 'c-1' });
    rerender({ id: 'c-1' });
    await new Promise((r) => setTimeout(r, 10));

    const validateCalls = postMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('validate-draft'),
    );
    expect(validateCalls).toHaveLength(1);
    expect(validateCalls[0][1]).toMatchObject({
      original_raw: '{"foo":"bar"}',
      original_format: 'JSON',
    });
  });

  it('re-fires once when the contract id changes', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    postMock.mockResolvedValue({ data: validResult } as never);

    const { rerender } = renderHook(
      ({ id }: { id: string }) =>
        useAutoValidateContract({
          id,
          original_raw: '{}',
          original_format: 'JSON',
        }),
      {
        wrapper: makeWrapper(queryClient),
        initialProps: { id: 'c-1' },
      },
    );

    await waitFor(() => {
      const calls = postMock.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('validate-draft'),
      );
      expect(calls).toHaveLength(1);
    });

    rerender({ id: 'c-2' });

    await waitFor(() => {
      const calls = postMock.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('validate-draft'),
      );
      expect(calls).toHaveLength(2);
    });
  });

  it('surfaces status="warnings" with warning count', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    postMock.mockResolvedValue({ data: warnResult } as never);

    const { result } = renderHook(
      () =>
        useAutoValidateContract({
          id: 'c-warn',
          original_raw: '{}',
          original_format: 'JSON',
        }),
      { wrapper: makeWrapper(queryClient) },
    );

    await waitFor(() => {
      expect(result.current.status).toBe('warnings');
    });
    expect(result.current.warningCount).toBe(1);
  });

  it('under React StrictMode, commits the result despite dev double-invoke', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    postMock.mockResolvedValue({ data: validResult } as never);

    // StrictMode dev-mode intentionally mounts → cleans up → mounts again
    // on initial render; the hook must still end up in "valid" state
    // instead of getting stuck in "validating" because the first request
    // was cancelled and the guard never let a second one fire.
    const { result } = renderHook(
      () =>
        useAutoValidateContract({
          id: 'c-strict',
          original_raw: '{}',
          original_format: 'JSON',
        }),
      {
        wrapper: ({ children }: { children: ReactNode }) => (
          <StrictMode>
            <QueryClientProvider client={queryClient}>
              {children}
            </QueryClientProvider>
          </StrictMode>
        ),
      },
    );

    await waitFor(() => {
      expect(result.current.status).toBe('valid');
    });
  });

  it('surfaces status="invalid" with error summary', async () => {
    const postMock = vi.mocked(apiClient.getClient().post);
    postMock.mockResolvedValue({ data: invalidResult } as never);

    const { result } = renderHook(
      () =>
        useAutoValidateContract({
          id: 'c-bad',
          original_raw: '{}',
          original_format: 'JSON',
        }),
      { wrapper: makeWrapper(queryClient) },
    );

    await waitFor(() => {
      expect(result.current.status).toBe('invalid');
    });
    expect(result.current.errorSummary).toMatch(/missing required/i);
  });
});
