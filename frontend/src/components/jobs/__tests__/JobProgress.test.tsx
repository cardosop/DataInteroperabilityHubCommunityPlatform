/**
 * JobProgress Tests
 *
 * Comprehensive tests for the JobProgress component covering:
 * - Progress bar display
 * - Percentage display
 * - Current step display
 * - Indeterminate progress
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobProgress } from '../JobProgress'

describe('JobProgress', () => {
  describe('Progress Display', () => {
    it('should display progress percentage', () => {
      render(<JobProgress progress={65} />)

      expect(screen.getByText(/65%/i)).toBeInTheDocument()
    })

    it('should display progress bar', () => {
      render(<JobProgress progress={65} />)

      const progressBar = screen.getByRole('progressbar')
      expect(progressBar).toBeInTheDocument()
      expect(progressBar).toHaveAttribute('aria-valuenow', '65')
    })

    it('should display current step', () => {
      render(<JobProgress progress={65} currentStep="Validating data" />)

      expect(screen.getByText(/validating data/i)).toBeInTheDocument()
    })

    it('should handle indeterminate progress', () => {
      render(<JobProgress />)

      const progressBar = screen.getByRole('progressbar')
      expect(progressBar).not.toHaveAttribute('aria-valuenow')
    })

    it('should handle zero progress', () => {
      render(<JobProgress progress={0} />)

      expect(screen.getByText(/0%/i)).toBeInTheDocument()
    })

    it('should handle 100% progress', () => {
      render(<JobProgress progress={100} />)

      expect(screen.getByText(/100%/i)).toBeInTheDocument()
    })
  })
})

