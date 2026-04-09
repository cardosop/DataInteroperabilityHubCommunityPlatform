/**
 * Protected Route Component
 * Wraps routes that require authentication
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../features/auth/store/authStore';
import { LoadingSpinner } from './LoadingSpinner';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string[];
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, user, isLoading } = useAuthStore();
  const location = useLocation();

  // Phase 213.I.6 — this branch is now only hit on the rare cold-start
  // case where no stored user exists AND the cookie-based refresh flow
  // is in progress. After 213.I the store hydrates synchronously from
  // localStorage, so isLoading stays false for every normal page load.
  if (isLoading) {
    return <LoadingSpinner message="Loading..." />;
  }

  // Check authentication - if not authenticated, redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role requirements if specified
  if (requiredRole && user) {
    const hasRole = requiredRole.some(role => user.roles.includes(role));
    if (!hasRole) {
      return <Navigate to="/403" replace />;
    }
  }

  return <>{children}</>;
}
