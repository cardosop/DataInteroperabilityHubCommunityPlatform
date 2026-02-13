/**
 * App Providers
 * Wraps app with necessary providers (React Query, etc.)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useEffect } from 'react';
import { useAuthStore } from '../../features/auth/store/authStore';
import { performanceMetricsService } from '../../shared/services/performanceMetrics';
import { websocketClient } from '../../shared/services/websocketClient';

// Optimized QueryClient with better caching strategy
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes - data considered fresh
      gcTime: 10 * 60 * 1000, // 10 minutes - cache garbage collection (formerly cacheTime)
    },
    mutations: {
      retry: 0, // Don't retry mutations by default
    },
  },
});

interface AppProvidersProps {
  children: React.ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const { isAuthenticated, user } = useAuthStore();

  // Initialize WebSocket connection when authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      const token = localStorage.getItem('access_token');
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

  // Initialize performance metrics collection
  useEffect(() => {
    performanceMetricsService.collectWebVitals();
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
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
