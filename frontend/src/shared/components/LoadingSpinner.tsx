/**
 * Loading Spinner Component
 */

import './LoadingSpinner.css';

export function LoadingSpinner({ size = 'medium', message }: { size?: 'small' | 'medium' | 'large'; message?: string }) {
  return (
    <div className="loading-spinner-container">
      <div className={`loading-spinner loading-spinner-${size}`} role="status" aria-label="Loading">
        <span className="visually-hidden">Loading...</span>
      </div>
      {message && <p className="loading-spinner-message">{message}</p>}
    </div>
  );
}
