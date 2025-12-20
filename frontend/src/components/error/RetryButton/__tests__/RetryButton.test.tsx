/**
 * RetryButton Tests
 *
 * Comprehensive tests for the RetryButton component covering:
 * - Max retries enforcement
 * - Disabled state
 * - Retry count display
 * - Click handling
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RetryButton } from '../RetryButton'

describe('RetryButton', () => {
  describe('Rendering', () => {
    it('should render retry button', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} />)

      expect(screen.getByText(/retry/i)).toBeInTheDocument()
    })

    it('should display retry count when provided', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} retryCount={2} maxRetries={5} />)

      expect(screen.getByText(/2.*5/i)).toBeInTheDocument()
    })
  })

  describe('Max Retries', () => {
    it('should disable button when max retries reached', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} retryCount={3} maxRetries={3} />)

      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
    })

    it('should enable button when retry count is below max', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} retryCount={2} maxRetries={3} />)

      const button = screen.getByRole('button')
      expect(button).not.toBeDisabled()
    })

    it('should enable button when no max retries specified', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} retryCount={10} />)

      const button = screen.getByRole('button')
      expect(button).not.toBeDisabled()
    })
  })

  describe('Click Handling', () => {
    it('should call onRetry when clicked', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} />)

      const button = screen.getByRole('button')
      fireEvent.click(button)

      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('should not call onRetry when disabled', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} retryCount={3} maxRetries={3} />)

      const button = screen.getByRole('button')
      fireEvent.click(button)

      expect(onRetry).not.toHaveBeenCalled()
    })
  })

  describe('Variants', () => {
    it('should use contained variant by default', () => {
      const onRetry = vi.fn()
      const { container } = render(<RetryButton onRetry={onRetry} />)

      const button = container.querySelector('.MuiButton-contained')
      expect(button).toBeInTheDocument()
    })

    it('should use specified variant', () => {
      const onRetry = vi.fn()
      const { container } = render(<RetryButton onRetry={onRetry} variant="outlined" />)

      const button = container.querySelector('.MuiButton-outlined')
      expect(button).toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('should show loading state when isRetrying is true', () => {
      const onRetry = vi.fn()
      render(<RetryButton onRetry={onRetry} isRetrying={true} />)

      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
      expect(screen.getByText(/retrying/i)).toBeInTheDocument()
    })
  })
})

