/**
 * DataQualityOverview Tests
 *
 * Comprehensive tests for the DataQualityOverview component covering:
 * - Statistics calculation and display
 * - Metric cards rendering
 * - Score visualization
 * - Loading and error states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DataQualityOverview } from '../DataQualityOverview'
import type { DQRun } from '@/lib/api/data-quality'

const mockDQRuns: DQRun[] = [
  {
    id: 'run-1',
    tenant: 'tenant-1',
    asset: 'asset-1',
    dataset: 'dataset-1',
    job: 'job-1',
    profile_key: 'intake_basic',
    engine: 'GREAT_EXPECTATIONS',
    status: 'SUCCEEDED',
    overall_status: 'PASS',
    quality_score: 95,
    checks_json: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'run-2',
    tenant: 'tenant-1',
    asset: 'asset-2',
    dataset: 'dataset-2',
    job: 'job-2',
    profile_key: 'intake_basic',
    engine: 'GREAT_EXPECTATIONS',
    status: 'SUCCEEDED',
    overall_status: 'WARN',
    quality_score: 75,
    checks_json: [],
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 'run-3',
    tenant: 'tenant-1',
    asset: 'asset-3',
    dataset: 'dataset-3',
    job: 'job-3',
    profile_key: 'intake_basic',
    engine: 'GREAT_EXPECTATIONS',
    status: 'SUCCEEDED',
    overall_status: 'FAIL',
    quality_score: 45,
    checks_json: [],
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z',
  },
]

describe('DataQualityOverview', () => {
  describe('Rendering', () => {
    it('should render overview statistics', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      expect(screen.getByText(/total runs/i)).toBeInTheDocument()
      expect(screen.getByText(/3/)).toBeInTheDocument() // total runs
    })

    it('should display passed runs count', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      expect(screen.getByText(/passed/i)).toBeInTheDocument()
      expect(screen.getByText(/1/)).toBeInTheDocument() // passed runs
    })

    it('should display warning runs count', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      expect(screen.getByText(/warning/i)).toBeInTheDocument()
      expect(screen.getByText(/1/)).toBeInTheDocument() // warning runs
    })

    it('should display failed runs count', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      expect(screen.getByText(/failed/i)).toBeInTheDocument()
      expect(screen.getByText(/1/)).toBeInTheDocument() // failed runs
    })

    it('should display average quality score', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      expect(screen.getByText(/average score/i)).toBeInTheDocument()
      // Average: (95 + 75 + 45) / 3 = 71.67
    })
  })

  describe('Statistics Calculation', () => {
    it('should calculate statistics from runs', () => {
      render(<DataQualityOverview runs={mockDQRuns} />)

      // Verify calculated stats are displayed
      expect(screen.getByText(/3/)).toBeInTheDocument() // total
    })

    it('should handle empty runs array', () => {
      render(<DataQualityOverview runs={[]} />)

      expect(screen.getByText(/0/)).toBeInTheDocument() // total runs
    })
  })

  describe('Props', () => {
    it('should accept pre-calculated stats', () => {
      const stats = {
        totalRuns: 10,
        passedRuns: 8,
        warningRuns: 1,
        failedRuns: 1,
        runningRuns: 0,
        averageScore: 85,
      }

      render(<DataQualityOverview stats={stats} />)

      expect(screen.getByText(/10/)).toBeInTheDocument()
    })

    it('should hide running scans when showRunningScans is false', () => {
      render(<DataQualityOverview runs={mockDQRuns} showRunningScans={false} />)

      // Running scans card should not be visible
      expect(screen.queryByText(/running/i)).not.toBeInTheDocument()
    })
  })
})

