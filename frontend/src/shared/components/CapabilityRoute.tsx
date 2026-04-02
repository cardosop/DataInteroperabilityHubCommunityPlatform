/**
 * Capability Route Component
 * Wraps routes that require specific capabilities
 */

import { Navigate } from 'react-router-dom';
import { useCapabilities } from '../hooks/useCapabilities';
import { LoadingSpinner } from './LoadingSpinner';

interface CapabilityRouteProps {
  capability: string;
  children: React.ReactNode;
}

export function CapabilityRoute({ capability, children }: CapabilityRouteProps) {
  const { isCapabilityAvailable, isLoading } = useCapabilities();

  // Avoid false negatives before capabilities are loaded
  if (isLoading) {
    return <LoadingSpinner message="Loading..." />;
  }

  if (!isCapabilityAvailable(capability)) {
    const to = import.meta.env.VITE_MVP_MODE === 'true' ? '/coming-soon' : '/unavailable';
    return <Navigate to={to} state={{ capability }} replace />;
  }

  return <>{children}</>;
}
