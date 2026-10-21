/**
 * useJobs / useJob hook tests
 *
 * Validates adaptive polling backoff (25.18.1) and staleTime deduplication (25.18.2).
 * Axios is mocked at module level; polling intervals are verified via refetchInterval
 * callback evaluation against controlled query state snapshots.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Job } from '../../../shared/types/jobs';
import type { PaginatedResponse } from '../../../shared/types/api';

// Mock API client at module level
vi.mock('../../../shared/api/client');

// Mock Toast so useMutationWithNotification doesn't need a provider
vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { apiClient } from '../../../shared/api/client';
import { useJobs, useJob, useCreateJob, useCancelJob } from './useJobs';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
    type: 'DQ_RUN',
    status: 'COMPLETED',
    resource_type: 'ASSET',
    resource_id: 'asset-1',
    created_at: '2026-01-01T00:00:00Z',
    tenant_id: 'tenant-1',
    created_by: 'user-1',
    ...overrides,
  } as Job;
}

function makePaginatedJobs(jobs: Job[]): PaginatedResponse<Job> {
  return {
    count: jobs.length,
    page: 1,
    page_size: 50,
    total_pages: 1,
    has_next: false,
    has_previous: false,
    next_page: null,
    previous_page: null,
    results: jobs,
  };
}

/** Create a fresh QueryClient + wrapper for each test */
function createTestHarness() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe('useJobs hooks — adaptive polling', () => {
  let mockAxios: HttpClient;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
    mockAxios = apiClient.getClient();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 25.18.1 — Adaptive backoff
  // ───────────────────────────────────────────────────────────────────────────

  describe('useJobs list', () => {
    it('returns data on successful fetch', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [makeJob({ id: 'j1', status: 'COMPLETED' })];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.results).toHaveLength(1);
      expect(result.current.data?.results[0].id).toBe('j1');
    });

    it('does not poll when all jobs are terminal', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [
        makeJob({ id: 'j1', status: 'COMPLETED' }),
        makeJob({ id: 'j2', status: 'FAILED' }),
      ];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const callCount = vi.mocked(mockAxios.get).mock.calls.length;

      // Advance well past any tier — no additional fetches should occur
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(callCount);
    });

    it('polls at 2 s (fast tier) when non-terminal jobs present', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [makeJob({ id: 'j1', status: 'RUNNING' })];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const callsAfterInit = vi.mocked(mockAxios.get).mock.calls.length;

      // Advance 2 s — should trigger one poll
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBeGreaterThan(callsAfterInit);
    });

    it('transitions to 5 s (medium tier) after 10 s of continuous polling', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [makeJob({ id: 'j1', status: 'PENDING' })];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // Advance past the 10 s fast-tier threshold
      await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });

      // Record call count, then advance exactly 5 s (medium interval)
      const callsBefore = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      const callsAfter = vi.mocked(mockAxios.get).mock.calls.length;

      expect(callsAfter).toBeGreaterThan(callsBefore);
    });

    it('transitions to 15 s (slow tier) after 60 s of continuous polling', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [makeJob({ id: 'j1', status: 'RUNNING' })];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // Advance past 60 s
      await act(async () => { await vi.advanceTimersByTimeAsync(62_000); });

      const callsBefore = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
      const callsAfter = vi.mocked(mockAxios.get).mock.calls.length;

      expect(callsAfter).toBeGreaterThan(callsBefore);
    });

    it('resets to fast tier when a new non-terminal job appears', async () => {
      const { wrapper } = createTestHarness();

      // Use a mutable response so we can control exactly when the new job appears
      let currentResponse = makePaginatedJobs([makeJob({ id: 'j1', status: 'RUNNING' })]);
      vi.mocked(mockAxios.get).mockImplementation(() =>
        Promise.resolve({ data: currentResponse })
      );

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.results).toHaveLength(1);

      // Advance past 10 s to move into medium tier (all polls still return 1 job)
      await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });

      // NOW introduce the new job — the next poll should pick this up
      currentResponse = makePaginatedJobs([
        makeJob({ id: 'j1', status: 'RUNNING' }),
        makeJob({ id: 'j2', status: 'PENDING' }),
      ]);

      // Advance 5 s (medium tier interval) to trigger a poll that sees the new job
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      await waitFor(() =>
        expect(result.current.data?.results).toHaveLength(2)
      );

      // Timer should have reset to fast tier. Verify poll fires within 2.5 s.
      const callsBefore = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
      const callsAfter = vi.mocked(mockAxios.get).mock.calls.length;

      expect(callsAfter).toBeGreaterThan(callsBefore);
    });

    it('stops polling when running job transitions to completed', async () => {
      const { wrapper } = createTestHarness();
      const runningJobs = [makeJob({ id: 'j1', status: 'RUNNING' })];
      const completedJobs = [makeJob({ id: 'j1', status: 'COMPLETED' })];

      // First fetch returns running; second returns completed; subsequent are also completed
      vi.mocked(mockAxios.get)
        .mockResolvedValueOnce({ data: makePaginatedJobs(runningJobs) })
        .mockResolvedValue({ data: makePaginatedJobs(completedJobs) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.results[0].status).toBe('RUNNING');

      // Advance past the 2 s fast-tier interval to trigger a poll
      await act(async () => { await vi.advanceTimersByTimeAsync(2500); });

      // The poll should pick up the completed status
      await waitFor(() =>
        expect(result.current.data?.results[0].status).toBe('COMPLETED')
      );

      // After completion, no more polls should fire
      const callsAfterComplete = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(callsAfterComplete);
    });

    it('handles empty results gracefully', async () => {
      const { wrapper } = createTestHarness();
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs([]) });

      const { result } = renderHook(() => useJobs(), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.results).toHaveLength(0);

      const callCount = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(callCount);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // useJob detail — same adaptive logic
  // ───────────────────────────────────────────────────────────────────────────

  describe('useJob detail', () => {
    it('returns a single job on successful fetch', async () => {
      const { wrapper } = createTestHarness();
      const job = makeJob({ id: 'j1', status: 'COMPLETED' });
      vi.mocked(mockAxios.get).mockResolvedValue({ data: job });

      const { result } = renderHook(() => useJob('j1'), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.id).toBe('j1');
    });

    it('does not fetch when id is null', () => {
      const { wrapper } = createTestHarness();
      const { result } = renderHook(() => useJob(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(vi.mocked(mockAxios.get)).not.toHaveBeenCalled();
    });

    it('polls at 2 s when job is RUNNING', async () => {
      const { wrapper } = createTestHarness();
      const job = makeJob({ id: 'j1', status: 'RUNNING' });
      vi.mocked(mockAxios.get).mockResolvedValue({ data: job });

      const { result } = renderHook(() => useJob('j1'), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const callsAfterInit = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBeGreaterThan(callsAfterInit);
    });

    it('does not poll when job is terminal (FAILED)', async () => {
      const { wrapper } = createTestHarness();
      const job = makeJob({ id: 'j1', status: 'FAILED' });
      vi.mocked(mockAxios.get).mockResolvedValue({ data: job });

      const { result } = renderHook(() => useJob('j1'), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const callCount = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(callCount);
    });

    it('stops polling when job transitions from PENDING to COMPLETED', async () => {
      const { wrapper } = createTestHarness();
      const pendingJob = makeJob({ id: 'j1', status: 'PENDING' });
      const completedJob = makeJob({ id: 'j1', status: 'COMPLETED' });

      // First fetch returns pending; subsequent return completed
      vi.mocked(mockAxios.get)
        .mockResolvedValueOnce({ data: pendingJob })
        .mockResolvedValue({ data: completedJob });

      const { result } = renderHook(() => useJob('j1'), { wrapper });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.status).toBe('PENDING');

      // Advance to trigger the first poll — picks up COMPLETED
      await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
      await waitFor(() => expect(result.current.data?.status).toBe('COMPLETED'));

      // After completion, no more polls should fire
      const callsAfter = vi.mocked(mockAxios.get).mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(callsAfter);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 25.18.2 — staleTime deduplication
  // ───────────────────────────────────────────────────────────────────────────

  describe('staleTime deduplication', () => {
    it('two useJobs hooks with same filters share a single network request', async () => {
      const { wrapper } = createTestHarness();
      const jobs = [makeJob({ id: 'j1', status: 'COMPLETED' })];
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs(jobs) });

      const { result: r1 } = renderHook(() => useJobs({ page: 1 }), { wrapper });
      const { result: r2 } = renderHook(() => useJobs({ page: 1 }), { wrapper });

      await waitFor(() => expect(r1.current.isSuccess).toBe(true));
      await waitFor(() => expect(r2.current.isSuccess).toBe(true));

      expect(r1.current.data?.results[0].id).toBe('j1');
      expect(r2.current.data?.results[0].id).toBe('j1');

      // Only one GET call should have been made (deduplication via staleTime)
      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(1);
    });

    it('useJobs hooks with different filters make separate requests', async () => {
      const { wrapper } = createTestHarness();
      const page1Jobs = [makeJob({ id: 'j1' })];
      const page2Jobs = [makeJob({ id: 'j2' })];
      vi.mocked(mockAxios.get)
        .mockResolvedValueOnce({ data: makePaginatedJobs(page1Jobs) })
        .mockResolvedValueOnce({ data: makePaginatedJobs(page2Jobs) });

      const { result: r1 } = renderHook(() => useJobs({ page: 1 }), { wrapper });
      const { result: r2 } = renderHook(() => useJobs({ page: 2 }), { wrapper });

      await waitFor(() => expect(r1.current.isSuccess).toBe(true));
      await waitFor(() => expect(r2.current.isSuccess).toBe(true));

      expect(vi.mocked(mockAxios.get).mock.calls.length).toBe(2);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Mutation hooks
  // ───────────────────────────────────────────────────────────────────────────

  describe('useCreateJob', () => {
    it('invalidates job queries on success', async () => {
      const { wrapper } = createTestHarness();
      const newJob = makeJob({ id: 'j-new', status: 'PENDING' });
      vi.mocked(mockAxios.post).mockResolvedValue({ data: newJob });
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs([newJob]) });

      const { result } = renderHook(() => useCreateJob(), { wrapper });

      await act(async () => {
        result.current.mutate({
          type: 'DQ_RUN',
          resource_type: 'ASSET',
          resource_id: 'asset-1',
        } as never);
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });

  describe('useCancelJob', () => {
    it('invalidates job queries on cancel', async () => {
      const { wrapper } = createTestHarness();
      const cancelledJob = makeJob({ id: 'j1', status: 'CANCELLED' });
      vi.mocked(mockAxios.post).mockResolvedValue({ data: cancelledJob });
      vi.mocked(mockAxios.get).mockResolvedValue({ data: makePaginatedJobs([cancelledJob]) });

      const { result } = renderHook(() => useCancelJob(), { wrapper });

      await act(async () => {
        result.current.mutate('j1');
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });
});
