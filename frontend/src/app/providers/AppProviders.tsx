/**
 * App Providers
 * Wraps app with necessary providers (React Query, etc.)
 */

import { QueryClient, QueryClientProvider, keepPreviousData } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useEffect } from 'react';
import { ToastProvider } from '../../shared/components/Toast';
import { useAuthStore } from '../../features/auth/store/authStore';
import { initWebVitals } from '../../shared/services/performanceMetrics';
import { apiClient } from '../../shared/api/client';
import { websocketClient } from '../../shared/services/websocketClient';

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

const queryClient = createQueryClient();

interface AppProvidersProps {
  children: React.ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const { isAuthenticated, user } = useAuthStore();

  // Initialize WebSocket connection when authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      // Phase 11.1: access_token is no longer in localStorage; read from apiClient memory
      const token = apiClient.getAccessToken();
      if (token) {
        websocketClient.connect(token).catch(() => {
          // WebSocket may be unavailable (e.g. API served HTTP-only); real-time uses polling
          if (import.meta.env.DEV) {
            console.debug('WebSocket unavailable; real-time updates will use polling.');
          }
        });
      }
    } else {
      websocketClient.disconnect();
    }

    return () => {
      websocketClient.disconnect();
    };
  }, [isAuthenticated, user]);

  // Initialize performance metrics collection (runs once, self-cleans load listener)
  useEffect(() => {
    initWebVitals();
  }, []);

  // Global error handler
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      import('../../shared/services/errorReporting').then(({ errorReportingService }) => {
        errorReportingService.reportError(event.error || new Error(event.message), {
          componentStack: event.filename ? `at ${event.filename}:${event.lineno}` : undefined,
        });
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      import('../../shared/services/errorReporting').then(({ errorReportingService }) => {
        errorReportingService.reportError(event.reason || new Error('Unhandled promise rejection'));
      });
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {children}
      </ToastProvider>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
