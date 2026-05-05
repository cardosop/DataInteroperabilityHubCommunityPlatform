import { describe, it, expect } from 'vitest';
import { keepPreviousData } from '@tanstack/react-query';

import { createQueryClient } from './queryClient';

describe('AppProviders QueryClient defaults', () => {
  it('uses keepPreviousData as the placeholderData default', () => {
    // When the query key changes (e.g. user types in a list-page search),
    // React Query must keep the previous result visible so isLoading does NOT
    // flip to true. Without this, the `if (isLoading) return <Skeleton />`
    // early-return in every list page unmounts the search input and focus is
    // lost per keystroke. See docs/mvp-gate review / Track B root cause.
    const client = createQueryClient();
    const defaults = client.getDefaultOptions();

    expect(defaults.queries?.placeholderData).toBe(keepPreviousData);
  });

  it('preserves existing query defaults (retry, refetchOnWindowFocus, staleTime, gcTime)', () => {
    const client = createQueryClient();
    const defaults = client.getDefaultOptions();

    expect(defaults.queries?.refetchOnWindowFocus).toBe(true);
    expect(defaults.queries?.staleTime).toBe(5 * 60 * 1000);
    expect(defaults.queries?.gcTime).toBe(10 * 60 * 1000);
    expect(typeof defaults.queries?.retry).toBe('function');
  });

  it('preserves mutations.retry = 0 default', () => {
    const client = createQueryClient();
    const defaults = client.getDefaultOptions();

    expect(defaults.mutations?.retry).toBe(0);
  });

  it('retry function does not retry 404s but retries other failures once', () => {
    const client = createQueryClient();
    const defaults = client.getDefaultOptions();
    const retry = defaults.queries?.retry;

    if (typeof retry !== 'function') {
      throw new Error('Expected retry to be a function');
    }

    // 404 → never retry
    const notFoundError = { response: { status: 404 } };
    expect(retry(0, notFoundError)).toBe(false);
    expect(retry(5, notFoundError)).toBe(false);

    // Non-404 HTTP error → retry once (failureCount 0 → true, 1 → false)
    const serverError = { response: { status: 500 } };
    expect(retry(0, serverError)).toBe(true);
    expect(retry(1, serverError)).toBe(false);

    // ApiError shape with http_status=404 → never retry
    const apiNotFound = { error: { http_status: 404 } };
    expect(retry(0, apiNotFound)).toBe(false);

    // Generic error (no status info) → retry once
    const generic = new Error('network failure');
    expect(retry(0, generic)).toBe(true);
    expect(retry(1, generic)).toBe(false);
  });
});
