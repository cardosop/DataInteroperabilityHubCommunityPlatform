/**
 * RegistrationRoute
 * Gating for /register based on capability + config.
 */
import { Navigate } from 'react-router-dom';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';

export function RegistrationRoute({ children }: { children: React.ReactNode }) {
  const { isCapabilityAvailable, isLoading } = useCapabilities();

  const registrationEnabledEnv = (import.meta.env.VITE_AUTH_REGISTRATION_ENABLED as string | undefined) ?? 'auto';
  const enabled =
    registrationEnabledEnv === 'auto' ? isCapabilityAvailable('auth.register') : registrationEnabledEnv === 'true';

  if (isLoading) {
    return <LoadingSpinner message="Loading..." />;
  }

  if (!enabled) {
    return <Navigate to="/unavailable" state={{ capability: 'auth.register' }} replace />;
  }

  return <>{children}</>;
}

