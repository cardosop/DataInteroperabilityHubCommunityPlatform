/**
 * Main App Component
 */

import { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import './App.css';
import { AppProviders } from './app/providers/AppProviders';
import { router } from './app/routes/routes';
import { useAuthStore } from './features/auth/store/authStore';
import { ErrorBoundary } from './shared/components/ErrorBoundary';

function App() {
  const { initialize } = useAuthStore();

  useEffect(() => {
    // Initialize auth state from storage
    initialize();
  }, [initialize]);

  return (
    <ErrorBoundary>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </ErrorBoundary>
  );
}

export default App;
