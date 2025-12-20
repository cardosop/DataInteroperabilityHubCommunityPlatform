/**
 * ErrorMessageDisplay Tests
 *
 * Comprehensive tests for the ErrorMessageDisplay component covering:
 * - Error message display
 * - Suggested actions rendering
 * - Help links rendering
 * - Next steps display
 * - i18n integration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorMessageDisplay } from '../ErrorMessageDisplay'
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

describe('ErrorMessageDisplay', () => {
  describe('Rendering', () => {
    it('should display error title and message', () => {
      const axiosError = {
        response: { status: 404 },
      } as AxiosError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)

      render(<ErrorMessageDisplay error={apiError} />)

      expect(screen.getByText(/page not found/i)).toBeInTheDocument()
      expect(screen.getByText(/couldn't find/i)).toBeInTheDocument()
    })

    it('should display error details when available', () => {
      const axiosError = {
        response: { status: 500 },
      } as AxiosError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)

      render(<ErrorMessageDisplay error={apiError} showDetails={true} />)

      expect(screen.getByText(/temporary issue/i)).toBeInTheDocument()
    })

    it('should hide details when showDetails is false', () => {
      const axiosError = {
        response: { status: 500 },
      } as AxiosError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)

      render(<ErrorMessageDisplay error={apiError} showDetails={false} />)

      // Details should not be visible
      const details = screen.queryByText(/temporary issue/i)
      expect(details).not.toBeInTheDocument()
    })
  })

  describe('Suggested Actions', () => {
    it('should display suggested actions', () => {
      const axiosError = {
        response: { status: 403 },
      } as AxiosError

      const apiError = new ApiError('Forbidden', 'FORBIDDEN', 403, axiosError)

      render(<ErrorMessageDisplay error={apiError} showActions={true} />)

      expect(screen.getByText(/contact administrator/i)).toBeInTheDocument()
      expect(screen.getByText(/go back/i)).toBeInTheDocument()
    })

    it('should hide actions when showActions is false', () => {
      const axiosError = {
        response: { status: 403 },
      } as AxiosError

      const apiError = new ApiError('Forbidden', 'FORBIDDEN', 403, axiosError)

      render(<ErrorMessageDisplay error={apiError} showActions={false} />)

      // Actions should not be visible
      const action = screen.queryByText(/contact administrator/i)
      expect(action).not.toBeInTheDocument()
    })
  })

  describe('Help Links', () => {
    it('should display help links', () => {
      const axiosError = {
        response: { status: 500 },
      } as AxiosError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)

      render(<ErrorMessageDisplay error={apiError} showHelpLinks={true} />)

      expect(screen.getByText(/status page/i)).toBeInTheDocument()
      expect(screen.getByText(/support center/i)).toBeInTheDocument()
    })

    it('should hide help links when showHelpLinks is false', () => {
      const axiosError = {
        response: { status: 500 },
      } as AxiosError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)

      render(<ErrorMessageDisplay error={apiError} showHelpLinks={false} />)

      // Help links should not be visible
      const link = screen.queryByText(/status page/i)
      expect(link).not.toBeInTheDocument()
    })
  })

  describe('Next Steps', () => {
    it('should display next steps', () => {
      const axiosError = {
        response: { status: 400 },
      } as AxiosError

      const apiError = new ApiError('Validation error', 'VALIDATION_ERROR', 400, axiosError)

      render(<ErrorMessageDisplay error={apiError} showNextSteps={true} />)

      expect(screen.getByText(/next steps/i)).toBeInTheDocument()
      expect(screen.getByText(/review the highlighted fields/i)).toBeInTheDocument()
    })

    it('should hide next steps when showNextSteps is false', () => {
      const axiosError = {
        response: { status: 400 },
      } as AxiosError

      const apiError = new ApiError('Validation error', 'VALIDATION_ERROR', 400, axiosError)

      render(<ErrorMessageDisplay error={apiError} showNextSteps={false} />)

      // Next steps should not be visible
      const steps = screen.queryByText(/next steps/i)
      expect(steps).not.toBeInTheDocument()
    })
  })

  describe('Severity', () => {
    it('should use correct severity for error', () => {
      const axiosError = {
        response: { status: 500 },
      } as AxiosError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)

      const { container } = render(<ErrorMessageDisplay error={apiError} />)
      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardError')
    })

    it('should use correct severity for warning', () => {
      const axiosError = {
        response: { status: 401 },
      } as AxiosError

      const apiError = new ApiError('Unauthorized', 'UNAUTHORIZED', 401, axiosError)

      const { container } = render(<ErrorMessageDisplay error={apiError} />)
      const alert = container.querySelector('.MuiAlert-root')
      expect(alert).toHaveClass('MuiAlert-standardWarning')
    })
  })
})

