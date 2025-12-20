/**
 * DataQualityCheckResult Tests
 *
 * Comprehensive tests for the DataQualityCheckResult component covering:
 * - Check result display
 * - Status indicators
 * - Check details
 * - Expandable sections
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DataQualityCheckResult } from '../DataQualityCheckResult'
import type { DQRunResults } from '@/lib/api/data-quality'

const mockCheck = {
  name: 'expect_column_values_to_not_be_null',
  type: 'null_check',
  status: 'FAIL' as const,
  result: {
    observed_value: 150,
    expected_value: 0,
    unexpected_count: 150,
  },
  expectation: 'Column should not contain null values',
  message: 'Found 150 null values in column',
  severity: 'HIGH',
}

describe('DataQualityCheckResult', () => {
  describe('Rendering', () => {
    it('should render check name', () => {
      render(<DataQualityCheckResult check={mockCheck} />)

      expect(screen.getByText(/expect_column_values_to_not_be_null/i)).toBeInTheDocument()
    })

    it('should render check type', () => {
      render(<DataQualityCheckResult check={mockCheck} />)

      expect(screen.getByText(/null_check/i)).toBeInTheDocument()
    })

    it('should render check status', () => {
      render(<DataQualityCheckResult check={mockCheck} />)

      expect(screen.getByText(/fail/i)).toBeInTheDocument()
    })

    it('should render check message', () => {
      render(<DataQualityCheckResult check={mockCheck} />)

      expect(screen.getByText(/found 150 null values/i)).toBeInTheDocument()
    })
  })

  describe('Status Indicators', () => {
    it('should display pass status correctly', () => {
      const passCheck = { ...mockCheck, status: 'PASS' as const }
      render(<DataQualityCheckResult check={passCheck} />)

      expect(screen.getByText(/pass/i)).toBeInTheDocument()
    })

    it('should display warning status correctly', () => {
      const warnCheck = { ...mockCheck, status: 'WARN' as const }
      render(<DataQualityCheckResult check={warnCheck} />)

      expect(screen.getByText(/warn/i)).toBeInTheDocument()
    })
  })

  describe('Expandable Details', () => {
    it('should show details when expanded', () => {
      render(<DataQualityCheckResult check={mockCheck} />)

      const expandButton = screen.getByLabelText(/show details/i)
      fireEvent.click(expandButton)

      expect(screen.getByText(/observed value/i)).toBeInTheDocument()
      expect(screen.getByText(/150/)).toBeInTheDocument()
    })
  })
})

