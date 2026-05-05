/**
 * Main App Component
 */

import { useEffect } from 'react';
import { HelmetProvider } from 'react-helmet-async';
import { RouterProvider } from 'react-router-dom';
import * as Sentry from '@sentry/react';
import './App.css';
import { AppProviders } from './app/providers/AppProviders';
import { router } from './app/routes/routes';
import { useAuthStore } from './features/auth/store/authStore';
import { APP_NAME } from './shared/constants/brand';
import { ErrorBoundary } from './shared/components/ErrorBoundary';

function App() {
  const { initialize } = useAuthStore();

  useEffect(() => {
    document.title = APP_NAME;
  }, []);

  useEffect(() => {
    // Initialize auth state from storage
    initialize();
  }, [initialize]);

  // Forward unhandled promise rejections to Sentry (with cleanup on unmount)
  useEffect(() => {
    const handler = (event: PromiseRejectionEvent) => {
      Sentry.captureException(event.reason, {
        extra: { type: 'unhandledrejection' },
      });
    };
    window.addEventListener('unhandledrejection', handler);
    return () => window.removeEventListener('unhandledrejection', handler);
  }, []);

  return (
    <ErrorBoundary>
      {/*
        Phase 230.9 (REQ-SEM-SEO-001) — HelmetProvider wraps the entire
        app so any descendant component can declaratively add <head>
        tags via <Helmet>. Public-page Schema.org JSON-LD injection
        depends on this. The provider has zero render cost when no
        Helmet child is mounted, so wrapping unconditionally is safe.
      */}
      <HelmetProvider>
        <AppProviders>
          <RouterProvider router={router} />
        </AppProviders>
      </HelmetProvider>
    </ErrorBoundary>
  );
}

export default App;
