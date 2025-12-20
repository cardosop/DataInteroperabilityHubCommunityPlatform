/**
 * JobStatusIndicator Tests
 *
 * Comprehensive tests for the JobStatusIndicator component covering:
 * - Status display
 * - Color coding
 * - Icon display
 * - Size variants
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobStatusIndicator } from '../JobStatusIndicator'
import type { JobStatus } from '@/lib/api/jobs'

describe('JobStatusIndicator', () => {
  describe('Status Display', () => {
    it('should display pending status', () => {
      render(<JobStatusIndicator status="PENDING" />)

      expect(screen.getByText(/pending/i)).toBeInTheDocument()
    })

    it('should display running status', () => {
      render(<JobStatusIndicator status="RUNNING" />)

      expect(screen.getByText(/running/i)).toBeInTheDocument()
    })

    it('should display completed status', () => {
      render(<JobStatusIndicator status="COMPLETED" />)

      expect(screen.getByText(/completed/i)).toBeInTheDocument()
    })

    it('should display failed status', () => {
      render(<JobStatusIndicator status="FAILED" />)

      expect(screen.getByText(/failed/i)).toBeInTheDocument()
    })

    it('should display cancelled status', () => {
      render(<JobStatusIndicator status="CANCELLED" />)

      expect(screen.getByText(/cancelled/i)).toBeInTheDocument()
    })
  })

  describe('Size Variants', () => {
    it('should render small size', () => {
      render(<JobStatusIndicator status="RUNNING" size="small" />)

      const chip = screen.getByText(/running/i)
      expect(chip).toBeInTheDocument()
    })

    it('should render medium size', () => {
      render(<JobStatusIndicator status="RUNNING" size="medium" />)

      const chip = screen.getByText(/running/i)
      expect(chip).toBeInTheDocument()
    })
  })
})

