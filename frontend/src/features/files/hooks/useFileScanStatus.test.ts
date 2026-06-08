/**
 * useFileScanStatus tests — Phase 260.3.D.
 *
 * Behavioral coverage for the scan-status polling hook. Replaces the
 * earlier hook-export-only smoke test which did not exercise any of the
 * polling / terminal-stop / cleanup contract that 260.3.D.4 claims to
 * cover.
 *
 * The fileService HTTP boundary is mocked at the module level (the
 * established pattern in this codebase, e.g.
 * src/shared/hooks/useUnreadBadgeCounts.test.tsx). The hook itself is
 * exercised end-to-end with renderHook + fake timers so the polling
 * cadence and cleanup paths are real.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/fileService', () => ({
  fileService: {
    getScanStatus: vi.fn(),
  },
}));

import { fileService } from '../services/fileService';
import { FileScanStatus } from '../../../shared/types/files';
import { useFileScanStatus } from './useFileScanStatus';

const getScanStatusMock = vi.mocked(fileService.getScanStatus);

/**
 * Drain pending microtasks so awaited Promise.then() callbacks inside
 * the hook's `tick()` complete before the test reads state. ``await
 * vi.advanceTimersByTimeAsync`` flushes timers and microtasks, but the
 * very first ``void tick()`` runs synchronously at mount (before any
 * timer is queued), so we need an explicit microtask drain after
 * renderHook before reading state.
 */
async function drainMicrotasks(): Promise<void> {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve();
  }
}

describe('useFileScanStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fetch and returns null state when fileId is null', () => {
    const { result } = renderHook(() => useFileScanStatus(null));

    expect(getScanStatusMock).not.toHaveBeenCalled();
    expect(result.current.scanStatus).toBeNull();
    expect(result.current.scannedAt).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('does not fetch when enabled=false', () => {
    getScanStatusMock.mockResolvedValue({
      scan_status: FileScanStatus.PENDING_SCAN,
      scanned_at: null,
    });

    const { result } = renderHook(() =>
      useFileScanStatus('file-123', { enabled: false })
    );

    expect(getScanStatusMock).not.toHaveBeenCalled();
    expect(result.current.scanStatus).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('fetches on mount and surfaces scan_status + scanned_at + isLoading→false', async () => {
    vi.useFakeTimers();
    getScanStatusMock.mockResolvedValue({
      scan_status: FileScanStatus.PENDING_SCAN,
      scanned_at: null,
    });

    const { result } = renderHook(() => useFileScanStatus('file-abc'));

    await act(async () => {
      await drainMicrotasks();
    });

    expect(getScanStatusMock).toHaveBeenCalledTimes(1);
    expect(getScanStatusMock).toHaveBeenCalledWith('file-abc');
    expect(result.current.scanStatus).toBe(FileScanStatus.PENDING_SCAN);
    expect(result.current.scannedAt).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('polls every 2 s while scan_status is PENDING_SCAN', async () => {
    vi.useFakeTimers();
    getScanStatusMock.mockResolvedValue({
      scan_status: FileScanStatus.PENDING_SCAN,
      scanned_at: null,
    });

    renderHook(() => useFileScanStatus('file-poll'));

    await act(async () => {
      await drainMicrotasks();
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(3);

    // Sub-2 s tick must NOT fire another poll.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(3);
  });

  it('stops polling once the scan reaches a terminal state (CLEAN)', async () => {
    vi.useFakeTimers();
    getScanStatusMock
      .mockResolvedValueOnce({
        scan_status: FileScanStatus.PENDING_SCAN,
        scanned_at: null,
      })
      .mockResolvedValueOnce({
        scan_status: FileScanStatus.CLEAN,
        scanned_at: '2026-05-05T00:00:00Z',
      });

    const { result } = renderHook(() => useFileScanStatus('file-terminal'));

    await act(async () => {
      await drainMicrotasks();
    });
    expect(result.current.scanStatus).toBe(FileScanStatus.PENDING_SCAN);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.scanStatus).toBe(FileScanStatus.CLEAN);
    expect(result.current.scannedAt).toBe('2026-05-05T00:00:00Z');
    expect(getScanStatusMock).toHaveBeenCalledTimes(2);

    // Polling MUST be cleared — advancing 4 more seconds must not fire.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(2);
  });

  it.each([
    FileScanStatus.INFECTED,
    FileScanStatus.SCAN_ERROR,
    FileScanStatus.SCAN_UNAVAILABLE,
  ])('stops polling once the scan reaches terminal state %s', async (terminal) => {
    vi.useFakeTimers();
    getScanStatusMock.mockResolvedValueOnce({
      scan_status: terminal,
      scanned_at: '2026-05-05T01:00:00Z',
    });

    const { result } = renderHook(() => useFileScanStatus('file-terminal'));

    await act(async () => {
      await drainMicrotasks();
    });
    expect(result.current.scanStatus).toBe(terminal);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(1);
  });

  it('captures fetch errors, clears isLoading, and continues polling for retry', async () => {
    vi.useFakeTimers();
    const networkErr = new Error('network down');
    getScanStatusMock
      .mockRejectedValueOnce(networkErr)
      .mockResolvedValueOnce({
        scan_status: FileScanStatus.PENDING_SCAN,
        scanned_at: null,
      });

    const { result } = renderHook(() => useFileScanStatus('file-err'));

    await act(async () => {
      await drainMicrotasks();
    });
    expect(result.current.error).toBe(networkErr);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.scanStatus).toBeNull();

    // Polling continues — next tick recovers.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.scanStatus).toBe(FileScanStatus.PENDING_SCAN);
    expect(result.current.error).toBeNull();
    expect(getScanStatusMock).toHaveBeenCalledTimes(2);
  });

  it('clears the polling interval on unmount', async () => {
    vi.useFakeTimers();
    getScanStatusMock.mockResolvedValue({
      scan_status: FileScanStatus.PENDING_SCAN,
      scanned_at: null,
    });

    const { unmount } = renderHook(() => useFileScanStatus('file-unmount'));
    await act(async () => {
      await drainMicrotasks();
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(getScanStatusMock).toHaveBeenCalledTimes(1);
  });

  it('ignores a late response that arrives after fileId changes', async () => {
    vi.useFakeTimers();
    let resolveFirst: (value: { scan_status: string; scanned_at: string | null }) => void = () => {};
    const firstPromise = new Promise<{ scan_status: string; scanned_at: string | null }>(
      (r) => {
        resolveFirst = r;
      }
    );
    getScanStatusMock.mockReturnValueOnce(firstPromise as never).mockResolvedValueOnce({
      scan_status: FileScanStatus.CLEAN,
      scanned_at: '2026-05-05T00:00:00Z',
    });

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useFileScanStatus(id),
      { initialProps: { id: 'file-1' } }
    );

    // Switch fileId before the first request resolves.
    rerender({ id: 'file-2' });

    // Resolve the stale request — it should be ignored (cancelled flag).
    resolveFirst({
      scan_status: FileScanStatus.PENDING_SCAN,
      scanned_at: null,
    });

    await act(async () => {
      await drainMicrotasks();
    });

    expect(result.current.scanStatus).toBe(FileScanStatus.CLEAN);
    expect(result.current.scannedAt).toBe('2026-05-05T00:00:00Z');
  });
});
