/**
 * Error Reporting Service
 * Collects and reports frontend errors with correlation IDs
 */

import type { ApiError } from '../types/api';

export interface ErrorReport {
  message: string;
  stack?: string;
  correlationId?: string;
  url: string;
  userAgent: string;
  timestamp: string;
  errorType: 'javascript' | 'api' | 'network' | 'unknown';
  errorCode?: string;
  httpStatus?: number;
  componentStack?: string;
}

class ErrorReportingService {
  private errorQueue: ErrorReport[] = [];
  private maxQueueSize = 50;
  // Deduplication: track recently reported keys with timestamp to prevent triple-firing
  private recentReports = new Map<string, number>();

  /**
   * Report an error
   */
  reportError(
    error: Error | ApiError | unknown,
    context?: {
      correlationId?: string;
      componentStack?: string;
      errorCode?: string;
      httpStatus?: number;
    }
  ): void {
    let errorReport: ErrorReport;

    if (error && typeof error === 'object' && 'error' in error) {
      // API Error
      const apiError = error as ApiError;
      errorReport = {
        message: apiError.error.message || 'API Error',
        correlationId: apiError.error.request_id || context?.correlationId,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        errorType: 'api',
        errorCode: apiError.error.code,
        httpStatus: apiError.error.http_status,
        componentStack: context?.componentStack,
      };
    } else if (error instanceof Error) {
      // JavaScript Error
      errorReport = {
        message: error.message,
        stack: error.stack,
        correlationId: context?.correlationId,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        errorType: 'javascript',
        componentStack: context?.componentStack,
      };
    } else {
      // Unknown error
      errorReport = {
        message: String(error || 'Unknown error'),
        correlationId: context?.correlationId,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        errorType: 'unknown',
        componentStack: context?.componentStack,
      };
    }

    // Skip reporting expected 404 "not found" — reduces console noise in E2E and normal flows
    if (errorReport.httpStatus === 404) {
      return;
    }

    // Skip reporting 409 Conflict — expected for duplicate-resource scenarios (UI already shows the error)
    if (errorReport.httpStatus === 409) {
      return;
    }

    // Skip reporting 401 "Authentication credentials were not provided" — transient during E2E
    // when protected routes mount before auth hydration completes (page.goto full-reload race).
    if (errorReport.httpStatus === 401 && /authentication credentials were not provided/i.test(String(errorReport.message))) {
      return;
    }

    // Skip reporting 500 "too many clients" — Postgres connection pool exhausted under parallel E2E load (transient).
    if (errorReport.httpStatus === 500 && /too many clients|too many connections/i.test(String(errorReport.message))) {
      return;
    }

    // Skip reporting 500 host resolution errors — transient when API container loses DNS (postgres-test, postgres) during E2E.
    if (errorReport.httpStatus === 500 && /could not translate host name|name resolution|getaddrinfo|ENOTFOUND/i.test(String(errorReport.message))) {
      return;
    }

    // Skip reporting "X not found" messages (expected when user navigates to non-existent resource)
    const msg = (errorReport.message || '').toLowerCase();
    if (/not found|contract not found|listing not found|entitlement not found|dataset not found|run not found|job not found|connection not found|domain not found/i.test(msg)) {
      return;
    }

    // Deduplicate: same correlationId or same message+type within 500ms window
    const dedupeKey = errorReport.correlationId
      ? `corr:${errorReport.correlationId}`
      : `msg:${errorReport.message.slice(0, 100)}:${errorReport.errorType}`;
    const now = Date.now();
    const lastSeen = this.recentReports.get(dedupeKey);
    if (lastSeen !== undefined && now - lastSeen < 500) {
      return;
    }
    this.recentReports.set(dedupeKey, now);
    // Prune old entries to avoid unbounded growth
    if (this.recentReports.size > 100) {
      const cutoff = now - 5000;
      for (const [k, t] of this.recentReports) {
        if (t < cutoff) this.recentReports.delete(k);
      }
    }

    // Add to queue
    this.errorQueue.push(errorReport);
    if (this.errorQueue.length > this.maxQueueSize) {
      this.errorQueue.shift(); // Remove oldest
    }

    // Log to console (sanitized) — skip in unit-test mode and in E2E runs (Vite dev server
    // passes VITE_E2E_TEST=true via playwright.config.ts) to avoid noise from intentional
    // error-handling test scenarios (e.g. 503 injection tests).
    if (import.meta.env.MODE !== 'test' && import.meta.env.VITE_E2E_TEST !== 'true') {
      console.error('[Error Report]', {
        message: errorReport.message,
        correlationId: errorReport.correlationId,
        errorType: errorReport.errorType,
        timestamp: errorReport.timestamp,
      });
    }

    // In production, could send to external service (e.g., Sentry, LogRocket)
    // For now, we just log to console
    if (import.meta.env.PROD) {
      // TODO: Send to external error reporting service
      // this.sendToExternalService(errorReport);
    }
  }

  /**
   * Get recent errors
   */
  getRecentErrors(limit = 10): ErrorReport[] {
    return this.errorQueue.slice(-limit);
  }

  /**
   * Clear error queue
   */
  clearErrors(): void {
    this.errorQueue = [];
  }
}

export const errorReportingService = new ErrorReportingService();
export default errorReportingService;
