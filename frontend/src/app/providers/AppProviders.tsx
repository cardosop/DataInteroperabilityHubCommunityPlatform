/**
 * App Providers
 * Wraps app with necessary providers (React Query, etc.)
 */

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useEffect } from 'react';
import { ToastProvider } from '../../shared/components/Toast';
import { useToast } from '../../shared/components/Toast/useToast';
import { useAuthStore } from '../../features/auth/store/authStore';
import { initWebVitals } from '../../shared/services/performanceMetrics';
import { apiClient } from '../../shared/api/client';
import { websocketClient } from '../../shared/services/websocketClient';
import { createQueryClient } from './queryClient';

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
        <DeprecationInterceptorBridge />
        {children}
      </ToastProvider>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

/**
 * Phase 250.3.B.6 — wires ``deprecationInterceptor`` to the
 * in-tree toast surface + the auth store's admin flag once both
 * are mounted. Renders nothing; runs once on mount and rewires
 * when the auth state changes (so a logout-then-login picks up
 * the new admin status).
 */
function DeprecationInterceptorBridge() {
  const toast = useToast();
  const user = useAuthStore((s) => s.user);
  useEffect(() => {
    let cancelled = false;
    void import('../../shared/api/deprecationInterceptor').then((mod) => {
      if (cancelled) return;
      mod.configureDeprecationInterceptor({
        toast: {
          warning: (m: string) => toast.error(m),
          error: (m: string) => toast.error(m),
          info: (m: string) => toast.info(m),
        },
        isAdminSession: () => {
          if (!user) return false;
          if (user.is_platform_admin) return true;
          const roles = user.roles || [];
          return roles.includes('TENANT_ADMIN') || roles.includes('PLATFORM_ADMIN');
        },
      });
    });
    return () => {
      cancelled = true;
    };
  }, [toast, user]);
  return null;
}
