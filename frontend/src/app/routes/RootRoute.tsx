/**
 * Root Route
 * Single route / with auth-based switch: unauthenticated → Landing (at / only), authenticated → App shell (dashboard).
 * Unauthenticated access to protected paths (e.g. /assets) redirects to /login.
 * Avoids redirect chains; no separate /landing redirect.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../features/auth/store/authStore';
import { AppShell } from '../../features/shell/components/AppShell';
import { LoadingSpinner } from '../../shared/components/LoadingSpinner';
import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { LandingPage } from '../pages/LandingPage';
import './RootRoute.css';

export function RootRoute() {
  const { isAuthenticated, isLoading } = useAuthStore();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="root-route-loading">
        <LoadingSpinner message="Checking authentication…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    const pathname = location.pathname || '/';
    const isRoot = pathname === '/' || pathname === '';
    if (isRoot) {
      return <LandingPage />;
    }
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <ProtectedRoute>
      <AppShell />
    </ProtectedRoute>
  );
}
