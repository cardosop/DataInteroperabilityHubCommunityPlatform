/**
 * Loading Spinner Component
 */

import './LoadingSpinner.css';

export function LoadingSpinner({ size = 'medium', message }: { size?: 'small' | 'medium' | 'large'; message?: string }) {
  const ariaLabel = message ?? 'Loading';
  return (
    <div className="loading-spinner-container" role="status" aria-live="polite" aria-label={ariaLabel}>
      <div className={`loading-spinner loading-spinner-${size}`} aria-hidden="true" />
      {message && <p className="loading-spinner-message">{message}</p>}
    </div>
  );
}
