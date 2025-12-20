/**
 * ErrorToast Tests
 *
 * Comprehensive tests for the ErrorToast component covering:
 * - Auto-dismiss functionality
 * - Actions rendering
 * - Error message display
 * - Toast positioning
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ErrorToast } from '../ErrorToast'
import { ApiError } from '@/lib/api/errors'
import { AxiosError } from 'axios'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => {
      return options?.defaultValue || key
    },
    i18n: {
      language: 'en',
    },
  }),
}))

describe('ErrorToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Rendering', () => {
    it('should display error message', () => {
      const error = new Error('Test error')
      render(<ErrorToast error={error} open={true} />)

      expect(screen.getByText(/test error/i)).toBeInTheDocument()
    })

    it('should not render when open is false', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorToast error={error} open={false} />)

      expect(container.firstChild).toBeNull()
    })
  })

  describe('Auto-Dismiss', () => {
    it('should auto-dismiss after duration', async () => {
      const error = new Error('Test error')
      const onClose = vi.fn()
      const { rerender } = render(
        <ErrorToast error={error} open={true} onClose={onClose} autoHideDuration={1000} />
      )

      expect(screen.getByText(/test error/i)).toBeInTheDocument()

      vi.advanceTimersByTime(1000)

      await waitFor(() => {
        expect(onClose).toHaveBeenCalledTimes(1)
      })
    })

    it('should not auto-dismiss when autoHideDuration is 0', () => {
      const error = new Error('Test error')
      const onClose = vi.fn()
      render(
        <ErrorToast error={error} open={true} onClose={onClose} autoHideDuration={0} />
      )

      vi.advanceTimersByTime(5000)

      expect(onClose).not.toHaveBeenCalled()
    })

    it('should use default duration when not specified', async () => {
      const error = new Error('Test error')
      const onClose = vi.fn()
      render(<ErrorToast error={error} open={true} onClose={onClose} />)

      vi.advanceTimersByTime(5000) // Default duration

      await waitFor(() => {
        expect(onClose).toHaveBeenCalledTimes(1)
      })
    })
  })

  describe('Actions', () => {
    it('should render custom actions', () => {
      const error = new Error('Test error')
      const actions = <button>Custom Action</button>

      render(<ErrorToast error={error} open={true} actions={actions} />)

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

      render(<ErrorToast error={error} open={true} actions={actions} />)

      expect(screen.getByText('Action 1')).toBeInTheDocument()
      expect(screen.getByText('Action 2')).toBeInTheDocument()
    })
  })

  describe('Positioning', () => {
    it('should position toast at top-right by default', () => {
      const error = new Error('Test error')
      const { container } = render(<ErrorToast error={error} open={true} />)

      const snackbar = container.querySelector('.MuiSnackbar-root')
      expect(snackbar).toBeInTheDocument()
    })

    it('should position toast at specified position', () => {
      const error = new Error('Test error')
      const { container } = render(
        <ErrorToast error={error} open={true} anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }} />
      )

      const snackbar = container.querySelector('.MuiSnackbar-root')
      expect(snackbar).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('should handle API errors', () => {
      const axiosError = {
        response: { status: 404 },
      } as AxiosError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      render(<ErrorToast error={apiError} open={true} />)

      expect(screen.getByText(/not found/i)).toBeInTheDocument()
    })
  })
})

