/**
 * Error Display Component
 */

import type { ApiError } from '../types/api';
import './ErrorDisplay.css';

interface ErrorDisplayProps {
  error: ApiError | Error | unknown;
  title?: string;
  onRetry?: () => void;
}

export function ErrorDisplay({ error, title = 'An error occurred', onRetry }: ErrorDisplayProps) {
  let errorMessage = 'An unexpected error occurred';
  let errorCode: string | undefined;
  let requestId: string | undefined;

  if (error && typeof error === 'object' && 'error' in error) {
    const apiError = error as ApiError;
    errorMessage = apiError.error.message || errorMessage;
    errorCode = apiError.error.code;
    requestId = apiError.error.request_id;

    // Report error with correlation ID
    import('../services/errorReporting').then(({ errorReportingService }) => {
      errorReportingService.reportError(apiError, {
        correlationId: requestId,
      });
    });
  } else if (error instanceof Error) {
    errorMessage = error.message;

    // Report JavaScript error
    import('../services/errorReporting').then(({ errorReportingService }) => {
      errorReportingService.reportError(error);
    });
  } else if (typeof error === 'string') {
    errorMessage = error;
  }

  // Sanitize error message to prevent leaking sensitive data
  // Remove potential secrets (tokens, passwords, etc.)
  errorMessage = errorMessage.replace(
    /(password|token|secret|api[_-]?key|authorization|bearer|access[_-]?token|refresh[_-]?token|credential|private[_-]?key)[=:]\s*[^\s]+/gi,
    '[REDACTED]'
  );

  return (
    <div className="error-display" role="alert">
      <div className="error-display-icon">⚠️</div>
      <h3 className="error-display-title">{title}</h3>
      <p className="error-display-message">{errorMessage}</p>
      {errorCode && (
        <p className="error-display-code">
          Error Code: <code>{errorCode}</code>
        </p>
      )}
      {requestId && (
        <p className="error-display-request-id">
          Request ID: <code>{requestId}</code>
        </p>
      )}
      {onRetry && (
        <button className="error-display-retry" onClick={onRetry} type="button">
          Retry
        </button>
      )}
    </div>
  );
}
