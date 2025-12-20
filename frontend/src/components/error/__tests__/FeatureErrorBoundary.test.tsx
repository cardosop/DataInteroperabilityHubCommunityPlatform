/**
 * FeatureErrorBoundary Tests
 *
 * Comprehensive tests for the FeatureErrorBoundary component.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { FeatureErrorBoundary } from '../FeatureErrorBoundary'

// Component that throws an error
const ThrowError = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test error')
  }
  return <div>No error</div>
}

describe('FeatureErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for error boundary tests
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('should render children when there is no error', () => {
    render(
      <FeatureErrorBoundary feature="Test Feature">
        <div>Test content</div>
      </FeatureErrorBoundary>
    )

    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('should catch and display error when child component throws', () => {
    render(
      <FeatureErrorBoundary feature="Test Feature">
        <ThrowError shouldThrow={true} />
      </FeatureErrorBoundary>
    )

    expect(screen.getByText(/unable to load test feature/i)).toBeInTheDocument()
  })

  it('should display feature name in error message', () => {
    render(
      <FeatureErrorBoundary feature="Data Quality">
        <ThrowError shouldThrow={true} />
      </FeatureErrorBoundary>
    )

    expect(screen.getByText(/unable to load data quality/i)).toBeInTheDocument()
  })

  it('should show retry button when onRetry is provided', () => {
    const onRetry = vi.fn()
    render(
      <FeatureErrorBoundary feature="Test Feature" onRetry={onRetry}>
        <ThrowError shouldThrow={true} />
      </FeatureErrorBoundary>
    )

    const retryButton = screen.getByText('Retry')
    expect(retryButton).toBeInTheDocument()

    fireEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalled()
  })

  it('should call onError callback when error is caught', () => {
    const onError = vi.fn()
    render(
      <FeatureErrorBoundary feature="Test Feature" onError={onError}>
        <ThrowError shouldThrow={true} />
      </FeatureErrorBoundary>
    )

    expect(onError).toHaveBeenCalled()
  })

  it('should use custom fallback when provided', () => {
    const customFallback = <div>Custom feature error</div>
    render(
      <FeatureErrorBoundary feature="Test Feature" fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </FeatureErrorBoundary>
    )

    expect(screen.getByText('Custom feature error')).toBeInTheDocument()
  })
})

