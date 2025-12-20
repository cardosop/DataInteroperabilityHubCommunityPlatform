/**
 * GlobalErrorBoundary Tests
 *
 * Comprehensive tests for the GlobalErrorBoundary component.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { GlobalErrorBoundary } from '../GlobalErrorBoundary'

// Component that throws an error
const ThrowError = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test error')
  }
  return <div>No error</div>
}

describe('GlobalErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for error boundary tests
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('should render children when there is no error', () => {
    render(
      <GlobalErrorBoundary>
        <div>Test content</div>
      </GlobalErrorBoundary>
    )

    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('should catch and display error when child component throws', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('should display error ID', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    expect(screen.getByText(/error id:/i)).toBeInTheDocument()
  })

  it('should call onError callback when error is caught', () => {
    const onError = vi.fn()
    render(
      <GlobalErrorBoundary onError={onError}>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    expect(onError).toHaveBeenCalled()
  })

  it('should reset error when Try Again is clicked', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    const tryAgainButton = screen.getByText('Try Again')
    fireEvent.click(tryAgainButton)

    // Error should be reset (component should re-render)
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
  })

  it('should reload page when Reload Page is clicked', () => {
    const reloadSpy = vi.spyOn(window.location, 'reload').mockImplementation(() => {})
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    const reloadButton = screen.getByText('Reload Page')
    fireEvent.click(reloadButton)

    expect(reloadSpy).toHaveBeenCalled()
    reloadSpy.mockRestore()
  })

  it('should navigate home when Go Home is clicked', () => {
    delete (window as any).location
    window.location = { href: '' } as any

    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    const goHomeButton = screen.getByText('Go Home')
    fireEvent.click(goHomeButton)

    expect(window.location.href).toBe('/')
  })

  it('should use custom fallback when provided', () => {
    const customFallback = <div>Custom error UI</div>
    render(
      <GlobalErrorBoundary fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    expect(screen.getByText('Custom error UI')).toBeInTheDocument()
  })

  it('should use custom fallback function when provided', () => {
    const customFallback = (error: Error) => <div>Error: {error.message}</div>
    render(
      <GlobalErrorBoundary fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    )

    expect(screen.getByText('Error: Test error')).toBeInTheDocument()
  })
})

