import { QueryClient, keepPreviousData } from '@tanstack/react-query';

import { registerIdentityCacheInvalidator } from '../../shared/services/cacheIdentity';

/** Extract HTTP status from query error (Axios, ApiError, or generic). */
function getHttpStatusFromError(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const o = error as Record<string, unknown>;
  if (o.response && typeof o.response === 'object' && 'status' in o.response) {
    return (o.response as { status?: number }).status;
  }
  if (o.error && typeof o.error === 'object' && 'http_status' in o.error) {
    return (o.error as { http_status?: number }).http_status;
  }
  return undefined;
}

// Exported factory so tests can introspect defaults without re-declaring the config.
// `placeholderData: keepPreviousData` is load-bearing: it keeps previous data visible
// on query-key changes so `isLoading` does not flip to true. Without it, list pages
// with `if (isLoading) return <Skeleton />` unmount the search input per keystroke.
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        placeholderData: keepPreviousData,
        retry: (failureCount, error) => {
          const status = getHttpStatusFromError(error);
          if (status === 404) return false;
          return failureCount < 1;
        },
        refetchOnWindowFocus: true,
        staleTime: 5 * 60 * 1000,
        gcTime: 10 * 60 * 1000,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

/**
 * W5.2 (R2-F2) — the app-wide query client singleton.
 *
 * Query keys are NOT tenant-scoped: every list query under the same key
 * shares one cache entry regardless of the active tenant, so a tenant
 * switch (or a logout→login cycle) MUST drain the cache — otherwise a
 * tenant B render surfaces tenant A's cached rows (the exact leak the
 * identity-boundaries E2E pins). The singleton registers on the
 * identity cache bus: ``cancelQueries`` marks in-flight queries
 * cancelled (their resolutions must NOT commit data into the new
 * identity's cache) and ``clear`` empties the committed cache.
 */
export const queryClient = createQueryClient();

registerIdentityCacheInvalidator(() => {
  // Fire-and-forget: cancelQueries resolves when the abort signal
  // propagation settles; clear() is synchronous and the boundary
  // transition must never await the network.
  void queryClient.cancelQueries();
  queryClient.clear();
});
