/**
 * Error Context Capture Utilities
 *
 * Utilities for capturing contextual information when errors occur,
 * including user actions, application state, and request details.
 */

import type { Location } from 'react-router-dom'

/**
 * User action context
 */
export interface UserActionContext {
  /**
   * Action type (e.g., 'click', 'submit', 'navigate')
   */
  type: string
  /**
   * Action target (e.g., button ID, form name)
   */
  target?: string
  /**
   * Timestamp
   */
  timestamp: number
  /**
   * Additional action data
   */
  data?: Record<string, any>
}

/**
 * Application state context
 */
export interface AppStateContext {
  /**
   * Current route/path
   */
  route?: string
  /**
   * React Query cache state (simplified)
   */
  queryCache?: {
    queryCount: number
    mutationCount: number
  }
  /**
   * User session info (anonymized)
   */
  session?: {
    isAuthenticated: boolean
    userId?: string // Anonymized
    tenantId?: string // Anonymized
  }
  /**
   * Browser info
   */
  browser?: {
    userAgent: string
    language: string
    platform: string
    screenResolution?: string
  }
  /**
   * Network status
   */
  network?: {
    online: boolean
    connectionType?: string
  }
}

/**
 * Request context
 */
export interface RequestContext {
  /**
   * Request URL
   */
  url?: string
  /**
   * Request method
   */
  method?: string
  /**
   * Request ID (if available)
   */
  requestId?: string
  /**
   * Response status (if available)
   */
  status?: number
  /**
   * Request timestamp
   */
  timestamp?: number
}

/**
 * Complete error context
 */
export interface ErrorContext {
  /**
   * User actions leading up to error
   */
  userActions: UserActionContext[]
  /**
   * Application state at time of error
   */
  appState: AppStateContext
  /**
   * Request context (if applicable)
   */
  request?: RequestContext
  /**
   * Additional custom context
   */
  custom?: Record<string, any>
}

/**
 * User action history (last N actions)
 */
class UserActionHistory {
  private actions: UserActionContext[] = []
  private readonly maxActions: number

  constructor(maxActions: number = 10) {
    this.maxActions = maxActions
  }

  /**
   * Add a user action
   */
  add(action: Omit<UserActionContext, 'timestamp'>): void {
    this.actions.push({
      ...action,
      timestamp: Date.now(),
    })

    // Keep only last N actions
    if (this.actions.length > this.maxActions) {
      this.actions.shift()
    }
  }

  /**
   * Get recent actions
   */
  getRecent(count?: number): UserActionContext[] {
    if (count) {
      return this.actions.slice(-count)
    }
    return [...this.actions]
  }

  /**
   * Clear action history
   */
  clear(): void {
    this.actions = []
  }
}

/**
 * Global user action history
 */
export const userActionHistory = new UserActionHistory(10)

/**
 * Capture current application state
 *
 * @param location - React Router location (optional)
 * @returns Application state context
 */
export function captureAppState(location?: Location): AppStateContext {
  const state: AppStateContext = {}

  // Route information
  if (location) {
    state.route = location.pathname + location.search
  } else if (typeof window !== 'undefined') {
    state.route = window.location.pathname + window.location.search
  }

  // Browser information
  if (typeof navigator !== 'undefined') {
    state.browser = {
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      screenResolution:
        typeof screen !== 'undefined'
          ? `${screen.width}x${screen.height}`
          : undefined,
    }
  }

  // Network status
  if (typeof navigator !== 'undefined' && 'onLine' in navigator) {
    state.network = {
      online: navigator.onLine,
      connectionType:
        (navigator as any).connection?.effectiveType || undefined,
    }
  }

  // React Query cache state (if available)
  if (typeof window !== 'undefined' && (window as any).__REACT_QUERY_STATE__) {
    const queryState = (window as any).__REACT_QUERY_STATE__
    state.queryCache = {
      queryCount: queryState.queries?.length || 0,
      mutationCount: queryState.mutations?.length || 0,
    }
  }

  return state
}

/**
 * Capture complete error context
 *
 * @param error - Error that occurred
 * @param options - Additional context options
 * @returns Complete error context
 */
export function captureErrorContext(
  error: unknown,
  options?: {
    location?: Location
    request?: RequestContext
    custom?: Record<string, any>
    includeUserActions?: boolean
  }
): ErrorContext {
  const {
    location,
    request,
    custom,
    includeUserActions = true,
  } = options || {}

  return {
    userActions: includeUserActions ? userActionHistory.getRecent(5) : [],
    appState: captureAppState(location),
    request,
    custom,
  }
}

/**
 * Track a user action
 *
 * @param type - Action type
 * @param target - Action target
 * @param data - Additional data
 */
export function trackUserAction(
  type: string,
  target?: string,
  data?: Record<string, any>
): void {
  userActionHistory.add({ type, target, data })
}

