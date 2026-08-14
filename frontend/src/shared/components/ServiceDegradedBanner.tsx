/**
 * 302.4 — Generic service-degraded banner.
 *
 * Refactored from ``SemanticDegradedBanner`` to accept a ``serviceName``
 * prop so it can be reused across compliance, DQ, search, marketplace,
 * and any other service that surfaces a degraded state.
 *
 * a11y: ``<section role="alert" aria-live="polite">``
 */
import React from 'react';

export interface ServiceDegradedBannerProps {
  /** Human-readable service name (e.g. "Semantic Search", "Compliance"). */
  serviceName: string;
  /** Description of what's degraded and what the user should do. */
  message?: string;
  /** Retry CTA handler. Omit to hide the button. */
  onRetry?: () => void;
  /** Disable the button while mutation is in flight. */
  isRetrying?: boolean;
  /** Optional class name for layout. */
  className?: string;
}

export const ServiceDegradedBanner: React.FC<ServiceDegradedBannerProps> = ({
  serviceName,
  message,
  onRetry,
  isRetrying,
  className,
}) => {
  const retryDisabled = !onRetry || !!isRetrying;
  const defaultMessage = `${serviceName} is temporarily degraded. Your data is safe, but some features may be unavailable.`;

  return (
    <section
      role="alert"
      aria-live="polite"
      aria-label={`${serviceName} is degraded`}
      data-testid="service-degraded-banner"
      className={[
        'rounded-md border p-4 my-4 text-sm',
        'border-amber-300 bg-amber-50 text-amber-900',
        className ?? '',
      ].filter(Boolean).join(' ')}
    >
      <header className="flex items-baseline gap-2 mb-2">
        <span aria-hidden="true" className="text-lg leading-none">⚠</span>
        <h3 className="font-semibold text-base">{serviceName} Degraded</h3>
      </header>
      <p className="mb-3">{message || defaultMessage}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retryDisabled}
          data-testid="service-degraded-banner-retry"
          className="rounded border border-amber-700 bg-amber-100 hover:bg-amber-200 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1 text-sm font-medium"
        >
          {isRetrying ? 'Retrying…' : 'Retry'}
        </button>
      )}
    </section>
  );
};
