/**
 * ErrorBoundary Component
 *
 * React error boundary for catching and handling component errors.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import {
  Box,
  Container,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Paper,
  Stack,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Home as HomeIcon,
  BugReport as BugReportIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'
import { getErrorMessageConfig, getUserFriendlyErrorMessage } from '@/utils/errorMessages'

export interface ErrorBoundaryProps {
  /**
   * Children to render
   */
  children: ReactNode
  /**
   * Custom fallback UI
   */
  fallback?: ReactNode | ((error: Error, errorInfo: ErrorInfo) => ReactNode)
  /**
   * Error boundary name (for logging)
   */
  name?: string
  /**
   * Callback when error is caught
   */
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  /**
   * Show error details in development
   */
  showErrorDetails?: boolean
  /**
   * Reset error on navigation
   */
  resetOnNavigation?: boolean
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorId: string | null
}

/**
 * ErrorBoundary component
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // Generate unique error ID
    const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    return {
      hasError: true,
      error,
      errorId,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { name, onError } = this.props

    // Log error
    console.error(`[ErrorBoundary${name ? `: ${name}` : ''}]`, {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
      errorId: this.state.errorId,
    })

    // Track error using error logging service
    if (typeof window !== 'undefined') {
      // Use dynamic import to avoid blocking
      import('@/services/errorLogging')
        .then(({ logError }) => {
          logError(error, {
            context: {
              errorBoundary: name || 'Unknown',
              errorId: this.state.errorId,
              componentStack: errorInfo.componentStack,
              errorInfo: errorInfo.toString(),
            },
            tags: {
              error_boundary: name || 'Unknown',
              error_id: this.state.errorId,
            },
          })
        })
        .catch((importError) => {
          // Fallback to console if import fails
          console.error('[ErrorBoundary] Failed to import error logging service:', importError)
          if (window.Sentry) {
            window.Sentry.captureException(error, {
              tags: {
                errorBoundary: name || 'Unknown',
                errorId: this.state.errorId,
              },
              extra: {
                componentStack: errorInfo.componentStack,
                errorInfo: errorInfo.toString(),
              },
            })
          }
        })
    }

    // Update state with error info
    this.setState({ errorInfo })

    // Call custom error handler
    if (onError) {
      onError(error, errorInfo)
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    // Reset error on navigation if enabled
    if (this.props.resetOnNavigation && this.state.hasError) {
      const currentPath = window.location.pathname
      const prevPath = prevProps.children

      // Simple path comparison - in production, use proper routing detection
      if (currentPath !== prevPath) {
        this.resetError()
      }
    }
  }

  resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  render() {
    const { hasError, error, errorInfo, errorId } = this.state
    const { children, fallback, showErrorDetails = process.env.NODE_ENV === 'development' } = this.props

    if (hasError && error) {
      // Use custom fallback if provided
      if (fallback) {
        if (typeof fallback === 'function') {
          return fallback(error, errorInfo!)
        }
        return fallback
      }

      // Default error UI
      const errorConfig = getErrorMessageConfig(error)
      const userMessage = getUserFriendlyErrorMessage(error)

      return (
        <Container maxWidth="md" sx={{ padding: spacing[4], marginTop: spacing[4] }}>
          <Paper elevation={2} sx={{ padding: spacing[4] }}>
            <Alert severity={errorConfig.severity} sx={{ marginBottom: spacing[3] }}>
              <AlertTitle>{errorConfig.title}</AlertTitle>
              {userMessage}
            </Alert>

            <Box sx={{ marginBottom: spacing[3] }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Error ID: {errorId}
              </Typography>
              {showErrorDetails && (
                <Box
                  sx={{
                    marginTop: spacing[2],
                    padding: spacing[2],
                    backgroundColor: 'action.hover',
                    borderRadius: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    overflow: 'auto',
                    maxHeight: '300px',
                  }}
                >
                  <Typography variant="caption" fontWeight="bold" display="block" gutterBottom>
                    Error Details:
                  </Typography>
                  <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                    {error.toString()}
                    {errorInfo?.componentStack && (
                      <>
                        {'\n\nComponent Stack:'}
                        {errorInfo.componentStack}
                      </>
                    )}
                  </Typography>
                </Box>
              )}
            </Box>

            <Stack direction="row" spacing={2} flexWrap="wrap">
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={this.resetError}
              >
                Try Again
              </Button>
              <Button
                variant="outlined"
                startIcon={<HomeIcon />}
                onClick={this.handleGoHome}
              >
                Go Home
              </Button>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={this.handleReload}
              >
                Reload Page
              </Button>
              {errorConfig.action && errorConfig.action !== 'Retry' && (
                <Button
                  variant="text"
                  startIcon={<BugReportIcon />}
                  href={`mailto:support@example.com?subject=Error Report&body=Error ID: ${errorId}%0D%0AError: ${encodeURIComponent(error.message)}`}
                >
                  {errorConfig.action}
                </Button>
              )}
            </Stack>
          </Paper>
        </Container>
      )
    }

    return children
  }
}

/**
 * Higher-order component for error boundaries
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  return function WithErrorBoundaryComponent(props: P) {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <Component {...props} />
      </ErrorBoundary>
    )
  }
}

