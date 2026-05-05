import { QueryClient, keepPreviousData } from '@tanstack/react-query';

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
