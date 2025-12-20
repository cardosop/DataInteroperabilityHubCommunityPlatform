/**
 * Error Message Templates
 *
 * Comprehensive error message system with:
 * - User-friendly messages (no technical jargon)
 * - Contextual templates
 * - Suggested actions
 * - Help links
 * - Clear next steps
 * - i18n support
 */

import type { ApiError, NetworkError } from '@/lib/api/errors'

export type ErrorSeverity = 'error' | 'warning' | 'info'

export interface SuggestedAction {
  /**
   * Action label
   */
  label: string
  /**
   * Action handler
   */
  onClick: () => void | Promise<void>
  /**
   * Action variant
   */
  variant?: 'primary' | 'secondary' | 'default'
}

export interface HelpLink {
  /**
   * Link label
   */
  label: string
  /**
   * Link URL
   */
  url: string
  /**
   * Whether to open in new tab
   */
  external?: boolean
}

export interface ErrorMessageTemplate {
  /**
   * Error code/key
   */
  code: string
  /**
   * User-friendly title (non-technical)
   */
  title: string
  /**
   * User-friendly message (non-technical, contextual)
   */
  message: string
  /**
   * Detailed explanation (optional)
   */
  details?: string
  /**
   * Error severity
   */
  severity: ErrorSeverity
  /**
   * Suggested actions user can take
   */
  suggestedActions?: SuggestedAction[]
  /**
   * Help links for additional information
   */
  helpLinks?: HelpLink[]
  /**
   * Clear next steps
   */
  nextSteps?: string[]
  /**
   * Whether error is recoverable
   */
  recoverable: boolean
  /**
   * i18n translation key (for localization)
   */
  i18nKey?: string
}

/**
 * Error Message Templates
 *
 * All messages are:
 * - User-friendly (no technical jargon)
 * - Actionable (clear what user can do)
 * - Contextual (explains what happened)
 * - Helpful (provides next steps)
 */
export const ERROR_MESSAGE_TEMPLATES: Record<string, ErrorMessageTemplate> = {
  // Network Errors
  NETWORK_ERROR: {
    code: 'NETWORK_ERROR',
    title: 'Connection Problem',
    message: "We're having trouble connecting to our servers. This might be a temporary issue.",
    details: 'Please check your internet connection and try again.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Retry',
        onClick: () => window.location.reload(),
        variant: 'primary',
      },
      {
        label: 'Check Connection',
        onClick: () => {
          // Could open network settings or show connection status
          console.log('Check connection')
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Network Troubleshooting Guide',
        url: '/help/network-troubleshooting',
        external: false,
      },
    ],
    nextSteps: [
      'Check your internet connection',
      'Try refreshing the page',
      'If the problem persists, contact support',
    ],
    recoverable: true,
    i18nKey: 'errors.network.error',
  },

  TIMEOUT: {
    code: 'TIMEOUT',
    title: 'Request Taking Too Long',
    message: 'Your request is taking longer than expected. This might be due to a slow connection.',
    details: 'Please try again in a moment.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Try Again',
        onClick: () => window.location.reload(),
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Connection Speed Guide',
        url: '/help/connection-speed',
        external: false,
      },
    ],
    nextSteps: [
      'Wait a moment and try again',
      'Check your connection speed',
      'If this keeps happening, contact support',
    ],
    recoverable: true,
    i18nKey: 'errors.timeout',
  },

  OFFLINE: {
    code: 'OFFLINE',
    title: 'You're Offline',
    message: "It looks like you're not connected to the internet. Don't worry, your changes are saved locally.",
    details: 'Once you reconnect, we'll automatically sync your changes.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Check Connection',
        onClick: () => {
          console.log('Check connection')
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Offline Mode Guide',
        url: '/help/offline-mode',
        external: false,
      },
    ],
    nextSteps: [
      'Check your internet connection',
      'Your changes are saved and will sync when you reconnect',
      'You can continue working offline',
    ],
    recoverable: true,
    i18nKey: 'errors.offline',
  },

  // Authentication Errors
  UNAUTHORIZED: {
    code: 'UNAUTHORIZED',
    title: 'Session Expired',
    message: 'Your session has expired for security reasons. Please sign in again to continue.',
    details: 'This happens automatically after a period of inactivity.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Sign In',
        onClick: () => {
          window.location.href = '/login'
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Session Management',
        url: '/help/sessions',
        external: false,
      },
    ],
    nextSteps: [
      'Sign in again to continue',
      'Your work is saved automatically',
      'If this keeps happening, check your session settings',
    ],
    recoverable: true,
    i18nKey: 'errors.unauthorized',
  },

  AUTHENTICATION_FAILED: {
    code: 'AUTHENTICATION_FAILED',
    title: 'Sign In Failed',
    message: "We couldn't verify your credentials. Please check your email and password.",
    details: 'Make sure your caps lock is off and try again.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Try Again',
        onClick: () => {
          // Focus on email field or reset form
          console.log('Retry login')
        },
        variant: 'primary',
      },
      {
        label: 'Reset Password',
        onClick: () => {
          window.location.href = '/reset-password'
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Password Reset Guide',
        url: '/help/password-reset',
        external: false,
      },
      {
        label: 'Account Help',
        url: '/help/account',
        external: false,
      },
    ],
    nextSteps: [
      'Double-check your email and password',
      'Try resetting your password if you forgot it',
      'Contact support if you continue having issues',
    ],
    recoverable: true,
    i18nKey: 'errors.authentication.failed',
  },

  TOKEN_EXPIRED: {
    code: 'TOKEN_EXPIRED',
    title: 'Session Expired',
    message: 'Your session has expired. Please sign in again to continue.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Sign In',
        onClick: () => {
          window.location.href = '/login'
        },
        variant: 'primary',
      },
    ],
    nextSteps: ['Sign in again to continue'],
    recoverable: true,
    i18nKey: 'errors.token.expired',
  },

  // Authorization Errors
  FORBIDDEN: {
    code: 'FORBIDDEN',
    title: 'Access Denied',
    message: "You don't have permission to perform this action. This might be because you need additional permissions.",
    details: 'Contact your administrator if you believe you should have access.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Contact Administrator',
        onClick: () => {
          window.location.href = '/contact?subject=permission-request'
        },
        variant: 'primary',
      },
      {
        label: 'Go Back',
        onClick: () => {
          window.history.back()
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Permissions Guide',
        url: '/help/permissions',
        external: false,
      },
      {
        label: 'Contact Support',
        url: '/support',
        external: false,
      },
    ],
    nextSteps: [
      'Contact your administrator to request access',
      'Check if you need to be added to a specific group',
      'Review your current permissions in settings',
    ],
    recoverable: false,
    i18nKey: 'errors.forbidden',
  },

  PERMISSION_DENIED: {
    code: 'PERMISSION_DENIED',
    title: 'Permission Required',
    message: "You don't have the required permissions for this operation.",
    severity: 'error',
    suggestedActions: [
      {
        label: 'Request Access',
        onClick: () => {
          window.location.href = '/contact?subject=permission-request'
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Permission Help',
        url: '/help/permissions',
        external: false,
      },
    ],
    nextSteps: ['Contact your administrator to request the required permissions'],
    recoverable: false,
    i18nKey: 'errors.permission.denied',
  },

  // Validation Errors
  VALIDATION_ERROR: {
    code: 'VALIDATION_ERROR',
    title: 'Please Check Your Input',
    message: 'Some of the information you entered needs to be corrected before we can continue.',
    details: 'Please review the highlighted fields and make the necessary changes.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Review Fields',
        onClick: () => {
          // Scroll to first error field
          const firstError = document.querySelector('.Mui-error, [aria-invalid="true"]')
          firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          ;(firstError as HTMLElement)?.focus()
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Form Guidelines',
        url: '/help/forms',
        external: false,
      },
    ],
    nextSteps: [
      'Review the highlighted fields',
      'Check for required fields that are missing',
      'Make sure all information is in the correct format',
    ],
    recoverable: true,
    i18nKey: 'errors.validation',
  },

  INVALID_INPUT: {
    code: 'INVALID_INPUT',
    title: 'Invalid Information',
    message: 'The information you provided is not in the correct format. Please check and try again.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Review Input',
        onClick: () => {
          const firstError = document.querySelector('.Mui-error, [aria-invalid="true"]')
          firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        },
        variant: 'primary',
      },
    ],
    nextSteps: [
      'Check the format of your input',
      'Review the field requirements',
      'Try again with the correct format',
    ],
    recoverable: true,
    i18nKey: 'errors.validation.invalid',
  },

  REQUIRED_FIELD: {
    code: 'REQUIRED_FIELD',
    title: 'Missing Information',
    message: 'Some required fields are missing. Please fill them in to continue.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Fill Required Fields',
        onClick: () => {
          const firstRequired = document.querySelector('[required]:not([value])')
          firstRequired?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          ;(firstRequired as HTMLElement)?.focus()
        },
        variant: 'primary',
      },
    ],
    nextSteps: [
      'Look for fields marked with an asterisk (*)',
      'Fill in all required information',
      'Try submitting again',
    ],
    recoverable: true,
    i18nKey: 'errors.validation.required',
  },

  // Not Found Errors
  NOT_FOUND: {
    code: 'NOT_FOUND',
    title: 'Page Not Found',
    message: "We couldn't find what you're looking for. It may have been moved or deleted.",
    details: 'The page or resource you requested does not exist.',
    severity: 'info',
    suggestedActions: [
      {
        label: 'Go to Home',
        onClick: () => {
          window.location.href = '/'
        },
        variant: 'primary',
      },
      {
        label: 'Go Back',
        onClick: () => {
          window.history.back()
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Site Map',
        url: '/sitemap',
        external: false,
      },
    ],
    nextSteps: [
      'Check the URL for typos',
      'Use the navigation menu to find what you need',
      'Contact support if you believe this is an error',
    ],
    recoverable: false,
    i18nKey: 'errors.notFound',
  },

  RESOURCE_NOT_FOUND: {
    code: 'RESOURCE_NOT_FOUND',
    title: 'Resource Not Found',
    message: "The item you're looking for doesn't exist or has been removed.",
    severity: 'info',
    suggestedActions: [
      {
        label: 'Browse Resources',
        onClick: () => {
          window.location.href = '/resources'
        },
        variant: 'primary',
      },
    ],
    nextSteps: [
      'The resource may have been deleted',
      'Try searching for similar resources',
      'Check if you have the correct link',
    ],
    recoverable: false,
    i18nKey: 'errors.resource.notFound',
  },

  // Server Errors
  INTERNAL_SERVER_ERROR: {
    code: 'INTERNAL_SERVER_ERROR',
    title: 'Something Went Wrong',
    message: "We encountered an unexpected problem. Don't worry, we've been notified and are working on it.",
    details: 'This is usually a temporary issue. Please try again in a few moments.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Try Again',
        onClick: () => {
          window.location.reload()
        },
        variant: 'primary',
      },
      {
        label: 'Contact Support',
        onClick: () => {
          window.location.href = '/support'
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Status Page',
        url: '/status',
        external: false,
      },
      {
        label: 'Support Center',
        url: '/support',
        external: false,
      },
    ],
    nextSteps: [
      'Wait a moment and try again',
      'Check our status page for known issues',
      'Contact support if the problem persists',
    ],
    recoverable: true,
    i18nKey: 'errors.server.internal',
  },

  SERVICE_UNAVAILABLE: {
    code: 'SERVICE_UNAVAILABLE',
    title: 'Service Temporarily Unavailable',
    message: 'The service is currently unavailable due to maintenance or high demand.',
    details: 'We are working to restore service as quickly as possible.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Check Status',
        onClick: () => {
          window.location.href = '/status'
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Status Page',
        url: '/status',
        external: false,
      },
    ],
    nextSteps: [
      'Check our status page for updates',
      'Try again in a few minutes',
      'Follow our status updates for restoration time',
    ],
    recoverable: true,
    i18nKey: 'errors.server.unavailable',
  },

  BAD_GATEWAY: {
    code: 'BAD_GATEWAY',
    title: 'Service Temporarily Unavailable',
    message: 'We are experiencing technical difficulties. Please try again in a moment.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Try Again',
        onClick: () => {
          window.location.reload()
        },
        variant: 'primary',
      },
    ],
    nextSteps: [
      'Wait a moment and try again',
      'Check our status page for updates',
      'Contact support if the problem continues',
    ],
    recoverable: true,
    i18nKey: 'errors.server.badGateway',
  },

  // Rate Limiting
  RATE_LIMIT_EXCEEDED: {
    code: 'RATE_LIMIT_EXCEEDED',
    title: 'Too Many Requests',
    message: "You've made too many requests in a short time. Please wait a moment before trying again.",
    details: 'This helps us ensure fair usage for all users.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Wait and Retry',
        onClick: () => {
          // Could show countdown timer
          console.log('Wait before retrying')
        },
        variant: 'primary',
      },
    ],
    helpLinks: [
      {
        label: 'Rate Limits Guide',
        url: '/help/rate-limits',
        external: false,
      },
    ],
    nextSteps: [
      'Wait a few moments before trying again',
      'Reduce the frequency of your requests',
      'Contact support if you need higher limits',
    ],
    recoverable: true,
    i18nKey: 'errors.rateLimit.exceeded',
  },

  TOO_MANY_REQUESTS: {
    code: 'TOO_MANY_REQUESTS',
    title: 'Please Slow Down',
    message: 'You are making requests too quickly. Please wait a moment and try again.',
    severity: 'warning',
    suggestedActions: [
      {
        label: 'Wait',
        onClick: () => {
          console.log('Wait before retrying')
        },
        variant: 'primary',
      },
    ],
    nextSteps: [
      'Wait a few seconds before trying again',
      'Reduce the speed of your actions',
    ],
    recoverable: true,
    i18nKey: 'errors.rateLimit.tooMany',
  },

  // Unknown Errors
  UNKNOWN_ERROR: {
    code: 'UNKNOWN_ERROR',
    title: 'Something Unexpected Happened',
    message: "An unexpected error occurred. We've been notified and are looking into it.",
    details: 'Please try again, or contact support if the problem persists.',
    severity: 'error',
    suggestedActions: [
      {
        label: 'Try Again',
        onClick: () => {
          window.location.reload()
        },
        variant: 'primary',
      },
      {
        label: 'Contact Support',
        onClick: () => {
          window.location.href = '/support'
        },
        variant: 'secondary',
      },
    ],
    helpLinks: [
      {
        label: 'Support Center',
        url: '/support',
        external: false,
      },
    ],
    nextSteps: [
      'Try refreshing the page',
      'Clear your browser cache and try again',
      'Contact support with details about what you were doing',
    ],
    recoverable: true,
    i18nKey: 'errors.unknown',
  },
}

/**
 * HTTP status code to error code mapping
 */
const HTTP_STATUS_MAP: Record<number, string> = {
  400: 'VALIDATION_ERROR',
  401: 'UNAUTHORIZED',
  403: 'FORBIDDEN',
  404: 'NOT_FOUND',
  408: 'TIMEOUT',
  429: 'RATE_LIMIT_EXCEEDED',
  500: 'INTERNAL_SERVER_ERROR',
  502: 'BAD_GATEWAY',
  503: 'SERVICE_UNAVAILABLE',
  504: 'TIMEOUT',
}

/**
 * Get error message template from error
 */
export function getErrorMessageTemplate(error: unknown): ErrorMessageTemplate {
  // Handle API errors
  if (error && typeof error === 'object' && 'code' in error) {
    const apiError = error as ApiError
    const errorCode = apiError.code.toUpperCase()

    // Check direct code match
    if (ERROR_MESSAGE_TEMPLATES[errorCode]) {
      return ERROR_MESSAGE_TEMPLATES[errorCode]
    }

    // Check HTTP status code mapping
    if (apiError.status && HTTP_STATUS_MAP[apiError.status]) {
      const mappedCode = HTTP_STATUS_MAP[apiError.status]
      if (ERROR_MESSAGE_TEMPLATES[mappedCode]) {
        return ERROR_MESSAGE_TEMPLATES[mappedCode]
      }
    }

    // Check for common error patterns in code
    if (errorCode.includes('NETWORK') || errorCode.includes('CONNECTION')) {
      return ERROR_MESSAGE_TEMPLATES.NETWORK_ERROR
    }
    if (errorCode.includes('TIMEOUT')) {
      return ERROR_MESSAGE_TEMPLATES.TIMEOUT
    }
    if (errorCode.includes('VALIDATION') || errorCode.includes('INVALID')) {
      return ERROR_MESSAGE_TEMPLATES.VALIDATION_ERROR
    }
    if (errorCode.includes('AUTH') || errorCode.includes('UNAUTHORIZED')) {
      return ERROR_MESSAGE_TEMPLATES.UNAUTHORIZED
    }
    if (errorCode.includes('FORBIDDEN') || errorCode.includes('PERMISSION')) {
      return ERROR_MESSAGE_TEMPLATES.FORBIDDEN
    }
    if (errorCode.includes('NOT_FOUND') || errorCode.includes('404')) {
      return ERROR_MESSAGE_TEMPLATES.NOT_FOUND
    }

    // Use server error for 5xx status codes
    if (apiError.status && apiError.status >= 500) {
      return ERROR_MESSAGE_TEMPLATES.INTERNAL_SERVER_ERROR
    }

    // Use validation error for 4xx status codes
    if (apiError.status && apiError.status >= 400 && apiError.status < 500) {
      return ERROR_MESSAGE_TEMPLATES.VALIDATION_ERROR
    }
  }

  // Handle network errors
  if (error && typeof error === 'object' && 'name' in error && (error as any).name === 'NetworkError') {
    const networkError = error as NetworkError
    // Check if offline
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      return ERROR_MESSAGE_TEMPLATES.OFFLINE
    }
    return ERROR_MESSAGE_TEMPLATES.NETWORK_ERROR
  }

  // Handle generic Error objects
  if (error instanceof Error) {
    const errorMessage = error.message.toUpperCase()

    if (errorMessage.includes('NETWORK') || errorMessage.includes('FETCH')) {
      return ERROR_MESSAGE_TEMPLATES.NETWORK_ERROR
    }
    if (errorMessage.includes('TIMEOUT')) {
      return ERROR_MESSAGE_TEMPLATES.TIMEOUT
    }
    if (errorMessage.includes('UNAUTHORIZED') || errorMessage.includes('AUTH')) {
      return ERROR_MESSAGE_TEMPLATES.UNAUTHORIZED
    }
    if (errorMessage.includes('FORBIDDEN') || errorMessage.includes('PERMISSION')) {
      return ERROR_MESSAGE_TEMPLATES.FORBIDDEN
    }
  }

  // Default to unknown error
  return ERROR_MESSAGE_TEMPLATES.UNKNOWN_ERROR
}

/**
 * Get user-friendly error message (non-technical)
 */
export function getUserFriendlyErrorMessage(error: unknown): string {
  const template = getErrorMessageTemplate(error)
  return template.message
}

/**
 * Get error title (non-technical)
 */
export function getErrorTitle(error: unknown): string {
  const template = getErrorMessageTemplate(error)
  return template.title
}

/**
 * Get suggested actions for error
 */
export function getSuggestedActions(error: unknown): SuggestedAction[] {
  const template = getErrorMessageTemplate(error)
  return template.suggestedActions || []
}

/**
 * Get help links for error
 */
export function getHelpLinks(error: unknown): HelpLink[] {
  const template = getErrorMessageTemplate(error)
  return template.helpLinks || []
}

/**
 * Get next steps for error
 */
export function getNextSteps(error: unknown): string[] {
  const template = getErrorMessageTemplate(error)
  return template.nextSteps || []
}

/**
 * Check if error is recoverable
 */
export function isRecoverableError(error: unknown): boolean {
  const template = getErrorMessageTemplate(error)
  return template.recoverable
}

