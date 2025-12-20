/**
 * GlobalErrorBoundary Component
 *
 * Global error boundary that wraps the entire application.
 * Catches all unhandled errors and displays a user-friendly error page.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import {
  Container,
  Box,
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
  ContactSupport as ContactSupportIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'
import { getErrorMessageConfig, getUserFriendlyErrorMessage } from '@/utils/errorMessages'

export interface GlobalErrorBoundaryProps {
  /**
   * Children to render
   */
  children: ReactNode
  /**
   * Custom fallback UI
   */
  fallback?: ReactNode | ((error: Error, errorInfo: ErrorInfo) => ReactNode)
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

interface GlobalErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorId: string | null
}

/**
 * GlobalErrorBoundary component
 * Wraps the entire application to catch unhandled errors
 */
export class GlobalErrorBoundary extends Component<GlobalErrorBoundaryProps, GlobalErrorBoundaryState> {
  private locationKey: string = ''

  constructor(props: GlobalErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<GlobalErrorBoundaryState> {
    // Generate unique error ID
    const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    return {
      hasError: true,
      error,
      errorId,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError } = this.props

    // Log error
    console.error('[GlobalErrorBoundary] Unhandled error:', {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
      errorId: this.state.errorId,
      location: window.location.href,
    })

    // Track error (e.g., Sentry)
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        tags: {
          errorBoundary: 'GlobalErrorBoundary',
          errorId: this.state.errorId,
        },
        extra: {
          componentStack: errorInfo.componentStack,
          errorInfo: errorInfo.toString(),
          location: window.location.href,
        },
      })
    }

    // Update state with error info
    this.setState({ errorInfo })

    // Call custom error handler
    if (onError) {
      onError(error, errorInfo)
    }
  }

  componentDidUpdate(prevProps: GlobalErrorBoundaryProps) {
    // Reset error on navigation if enabled
    if (this.props.resetOnNavigation && this.state.hasError) {
      const currentLocation = window.location.pathname
      if (currentLocation !== this.locationKey) {
        this.locationKey = currentLocation
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

  handleContactSupport = () => {
    const { error, errorId } = this.state
    const errorDetails = error
      ? `Error ID: ${errorId}\nError: ${encodeURIComponent(error.message)}\nLocation: ${encodeURIComponent(window.location.href)}`
      : `Error ID: ${errorId}`
    window.location.href = `mailto:support@example.com?subject=Error Report&body=${encodeURIComponent(errorDetails)}`
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
              <Button
                variant="text"
                startIcon={<ContactSupportIcon />}
                onClick={this.handleContactSupport}
              >
                Contact Support
              </Button>
            </Stack>
          </Paper>
        </Container>
      )
    }

    return children
  }
}

/**
 * Wrapper component that uses hooks (for location tracking)
 */
export const GlobalErrorBoundaryWithLocation: React.FC<Omit<GlobalErrorBoundaryProps, 'resetOnNavigation'>> = ({
  children,
  ...props
}) => {
  const location = useLocation()
  const locationKeyRef = React.useRef(location.key)

  React.useEffect(() => {
    locationKeyRef.current = location.key
  }, [location.key])

  return (
    <GlobalErrorBoundary
      {...props}
      resetOnNavigation={true}
    >
      {children}
    </GlobalErrorBoundary>
  )
}

