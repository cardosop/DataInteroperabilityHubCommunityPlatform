/**
 * Error Display Component
 */

import type { ApiError } from '../types/api';
import './ErrorDisplay.css';

interface ErrorDisplayProps {
  error?: ApiError | Error | unknown;
  message?: string;
  title?: string;
  onRetry?: () => void;
}

export function ErrorDisplay({ error, message, title = 'An error occurred', onRetry }: ErrorDisplayProps) {
  // Backward-compatible: accept either `error` or `message` prop.
  const resolvedError = error ?? message;
  let errorMessage = 'An unexpected error occurred';
  let errorCode: string | undefined;
  let requestId: string | undefined;

  if (resolvedError && typeof resolvedError === 'object' && 'error' in resolvedError) {
    const apiError = resolvedError as ApiError;
    errorMessage = apiError.error.message || errorMessage;
    errorCode = apiError.error.code;
    requestId = apiError.error.request_id;

    // Report error with correlation ID
    import('../services/errorReporting').then(({ errorReportingService }) => {
      errorReportingService.reportError(apiError, {
        correlationId: requestId,
      });
    });
  } else if (resolvedError instanceof Error) {
    errorMessage = resolvedError.message;

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
    // Phase 226.F1.b — data-testid added so e2e specs can use
    // `getByTestId('error-display')` instead of the fragile
    // `.locator('.error-display')` selector. Class kept for CSS.
    <div className="error-display" role="alert" data-testid="error-display">
      <div className="error-display-icon">⚠️</div>
      <h3 className="error-display-title" data-testid="error-display-title">{title}</h3>
      <p className="error-display-message" data-testid="error-display-message">{errorMessage}</p>
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
        <button
          className="error-display-retry"
          onClick={onRetry}
          type="button"
          data-testid="error-display-retry"
        >
          Retry
        </button>
      )}
    </div>
  );
}
