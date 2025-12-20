/**
 * ErrorAlert Tests
 *
 * Comprehensive tests for the ErrorAlert component covering:
 * - Severity variants
 * - Dismissible functionality
 * - Actions rendering
 * - Error message display
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorAlert } from '../ErrorAlert'
import { ApiError } from '@/lib/api/errors'
import { AxiosError } from 'axios'

describe('ErrorAlert', () => {
  describe('Rendering', () => {
    it('should display error message', () => {
      const error = new Error('Test error')
      render(<ErrorAlert error={error} />)

      expect(screen.getByText(/test error/i)).toBeInTheDocument()
    })

    it('should display error title when provided', () => {
      const error = new Error('Test error')
      render(<ErrorAlert error={error} title="Custom Title" />)

      expect(screen.getByText('Custom Title')).toBeInTheDocument()
    })
  })

  describe('Severity Variants', () => {
    it('should use error severity by default', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorAlert error={error} />)

      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardError')
    })

    it('should use warning severity when specified', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorAlert error={error} severity="warning" />)

      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardWarning')
    })

    it('should use info severity when specified', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorAlert error={error} severity="info" />)

      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardInfo')
    })

    it('should use success severity when specified', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorAlert error={error} severity="success" />)

      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardSuccess')
    })
  })

  describe('Dismissible', () => {
    it('should show close button when dismissible is true', () => {
      const error = new Error('Test error')
      render(<ErrorAlert error={error} dismissible={true} />)

      const closeButton = screen.getByLabelText(/close/i)
      expect(closeButton).toBeInTheDocument()
    })

    it('should hide close button when dismissible is false', () => {
      const error = new Error('Test error')
      render(<ErrorAlert error={error} dismissible={false} />)

      const closeButton = screen.queryByLabelText(/close/i)
      expect(closeButton).not.toBeInTheDocument()
    })

    it('should call onDismiss when close button is clicked', () => {
      const error = new Error('Test error')
      const onDismiss = vi.fn()
      render(<ErrorAlert error={error} dismissible={true} onDismiss={onDismiss} />)

      const closeButton = screen.getByLabelText(/close/i)
      fireEvent.click(closeButton)

      expect(onDismiss).toHaveBeenCalledTimes(1)
    })

    it('should hide alert when dismissed', () => {
      const error = new Error('Test error')
      const { container, rerender } = render(
        <ErrorAlert error={error} dismissible={true} />
      )

      const closeButton = screen.getByLabelText(/close/i)
      fireEvent.click(closeButton)

      rerender(<ErrorAlert error={error} dismissible={true} />)
      // Alert should be hidden after dismiss
      expect(container.querySelector('.MuiAlert-root')).not.toBeInTheDocument()
    })
  })

  describe('Actions', () => {
    it('should render custom actions', () => {
      const error = new Error('Test error')
      const actions = <button>Custom Action</button>

      render(<ErrorAlert error={error} actions={actions} />)

      expect(screen.getByText('Custom Action')).toBeInTheDocument()
    })

    it('should render multiple actions', () => {
      const error = new Error('Test error')
      const actions = (
        <>
          <button>Action 1</button>
          <button>Action 2</button>
        </>
      )

      render(<ErrorAlert error={error} actions={actions} />)

      expect(screen.getByText('Action 1')).toBeInTheDocument()
      expect(screen.getByText('Action 2')).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('should handle API errors', () => {
      const axiosError = {
        response: { status: 404 },
      } as AxiosError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      render(<ErrorAlert error={apiError} />)

      expect(screen.getByText(/not found/i)).toBeInTheDocument()
    })

    it('should handle unknown errors gracefully', () => {
      const unknownError = { someProperty: 'value' }
      render(<ErrorAlert error={unknownError} />)

      // Should display a generic error message
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })
  })
})

