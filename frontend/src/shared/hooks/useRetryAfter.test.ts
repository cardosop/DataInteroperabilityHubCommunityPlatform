/**
 * Phase 276.B.114 — useRetryAfter hook test.
 *
 * Verifies exponential backoff on 429 responses and max retries.
 */
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useRetryAfter } from './useRetryAfter';

describe('useRetryAfter', () => {
  it('returns the response on first success', async () => {
    const { result } = renderHook(() => useRetryAfter());
    const successResponse = new Response('ok', { status: 200 });

    const response = await result.current(async () => successResponse);

    expect(response.status).toBe(200);
  });

  it('retries on 429 with exponential backoff', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRetryAfter());

    let callCount = 0;
    const fn = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount < 3) {
        return Promise.resolve(
          new Response('rate limited', {
            status: 429,
            headers: { 'Retry-After': '1' },
          }),
        );
      }
      return Promise.resolve(new Response('ok', { status: 200 }));
    });

    const promise = result.current(fn, 3);
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    const response = await promise;
    expect(response.status).toBe(200);
    expect(fn).toHaveBeenCalledTimes(3);

    vi.useRealTimers();
  });

  it('respects max retries', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRetryAfter());

    const fn = vi.fn().mockResolvedValue(
      new Response('rate limited', {
        status: 429,
        headers: { 'Retry-After': '1' },
      }),
    );

    const promise = result.current(fn, 2);
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    const response = await promise;
    expect(response.status).toBe(429);
    expect(fn).toHaveBeenCalledTimes(3); // initial + 2 retries

    vi.useRealTimers();
  });
});
