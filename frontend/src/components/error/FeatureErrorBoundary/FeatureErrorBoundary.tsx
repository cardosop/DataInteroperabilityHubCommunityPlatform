/**
 * FeatureErrorBoundary Component
 *
 * Feature-level error boundary for isolating errors within specific features.
 * Provides a lightweight fallback UI that doesn't break the entire application.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Alert, AlertTitle, Box, Button, Typography } from '@mui/material'
import { Refresh as RefreshIcon } from '@mui/icons-material'
import { ErrorBoundary, ErrorBoundaryProps } from '../ErrorBoundary'
import { getErrorMessageConfig, getUserFriendlyErrorMessage } from '@/utils/errorMessages'

export interface FeatureErrorBoundaryProps {
  /**
   * Children to render
   */
  children: ReactNode
  /**
   * Feature name (for logging and display)
   */
  feature: string
  /**
   * Custom fallback UI
   */
  fallback?: ReactNode | ((error: Error, errorInfo: ErrorInfo) => ReactNode)
  /**
   * Callback when error is caught
   */
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  /**
   * Show error details
   */
  showErrorDetails?: boolean
  /**
   * Custom retry handler
   */
  onRetry?: () => void
}

/**
 * Default fallback UI for feature errors
 */
function DefaultFeatureFallback(
  error: Error,
  errorInfo: ErrorInfo,
  feature: string,
  onRetry?: () => void
) {
  const errorConfig = getErrorMessageConfig(error)
  const userMessage = getUserFriendlyErrorMessage(error)

  return (
    <Alert
      severity={errorConfig.severity}
      action={
        onRetry && (
          <Button
            color="inherit"
            size="small"
            startIcon={<RefreshIcon />}
            onClick={onRetry}
          >
            Retry
          </Button>
        )
      }
    >
      <AlertTitle>Unable to load {feature}</AlertTitle>
      <Typography variant="body2">{userMessage}</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
        Please refresh the page or try again later.
      </Typography>
    </Alert>
  )
}

/**
 * FeatureErrorBoundary component
 * Wraps specific features to isolate errors
 */
export const FeatureErrorBoundary: React.FC<FeatureErrorBoundaryProps> = ({
  children,
  feature,
  fallback,
  onError,
  showErrorDetails = false,
  onRetry,
}) => {
  const defaultFallback = (error: Error, errorInfo: ErrorInfo) =>
    DefaultFeatureFallback(error, errorInfo, feature, onRetry)

  return (
    <ErrorBoundary
      name={`Feature: ${feature}`}
      fallback={fallback || defaultFallback}
      onError={onError}
      showErrorDetails={showErrorDetails}
      resetOnNavigation={true}
    >
      {children}
    </ErrorBoundary>
  )
}

/**
 * Higher-order component for feature error boundaries
 */
export function withFeatureErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  featureName: string,
  errorBoundaryProps?: Omit<FeatureErrorBoundaryProps, 'children' | 'feature'>
) {
  return function WithFeatureErrorBoundaryComponent(props: P) {
    return (
      <FeatureErrorBoundary feature={featureName} {...errorBoundaryProps}>
        <Component {...props} />
      </FeatureErrorBoundary>
    )
  }
}

