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

    // Add to queue
    this.errorQueue.push(errorReport);
    if (this.errorQueue.length > this.maxQueueSize) {
      this.errorQueue.shift(); // Remove oldest
    }

    // Log to console (sanitized)
    console.error('[Error Report]', {
      message: errorReport.message,
      correlationId: errorReport.correlationId,
      errorType: errorReport.errorType,
      timestamp: errorReport.timestamp,
    });

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
