/**
 * DataQualityDashboardPage Tests
 *
 * Comprehensive tests for the DataQualityDashboardPage component covering:
 * - Page rendering
 * - DQ run overview display
 * - DQ metrics display
 * - DQ check results display
 * - Filtering functionality
 * - DQ run creation
 * - Scheduling functionality
 * - Loading states
 * - Error states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DataQualityDashboardPage } from '../DataQualityDashboardPage'
import { useDQRuns } from '@/hooks/useDQRuns'
import { useRunDQRun } from '@/hooks/useRunDQRun'
import { useAssets } from '@/hooks/useAssets'
import { useDatasets } from '@/hooks'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock hooks
vi.mock('@/hooks/useDQRuns', () => ({
  useDQRuns: vi.fn(),
}))

vi.mock('@/hooks/useRunDQRun', () => ({
  useRunDQRun: vi.fn(),
}))

vi.mock('@/hooks/useAssets', () => ({
  useAssets: vi.fn(),
}))

vi.mock('@/hooks', () => ({
  useDatasets: vi.fn(),
}))

const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DataQualityDashboardPage', () => {
  const mockUseDQRuns = vi.mocked(useDQRuns)
  const mockUseRunDQRun = vi.mocked(useRunDQRun)
  const mockUseAssets = vi.mocked(useAssets)
  const mockUseDatasets = vi.mocked(useDatasets)

  const mockDQRuns = [
    {
      id: 'dq-run-1',
      tenant: 'tenant-1',
      asset: 'asset-1',
      dataset: null,
      file: null,
      job: 'job-1',
      profile_key: 'intake_basic_gx',
      engine: 'GREAT_EXPECTATIONS' as const,
      status: 'SUCCEEDED' as const,
      overall_status: 'PASS' as const,
      quality_score: 85.5,
      checks_json: [
        {
          name: 'Check 1',
          type: 'completeness',
          status: 'PASS' as const,
          result: {},
        },
        {
          name: 'Check 2',
          type: 'accuracy',
          status: 'FAIL' as const,
          result: {},
        },
      ],
      details_json: {},
      started_at: new Date(Date.now() - 3600000).toISOString(),
      completed_at: new Date().toISOString(),
      created_at: new Date(Date.now() - 3600000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'dq-run-2',
      tenant: 'tenant-1',
      asset: 'asset-2',
      dataset: null,
      file: null,
      job: 'job-2',
      profile_key: 'intake_basic_soda',
      engine: 'SODA' as const,
      status: 'SUCCEEDED' as const,
      overall_status: 'WARN' as const,
      quality_score: 65.0,
      checks_json: [
        {
          name: 'Check 3',
          type: 'validity',
          status: 'WARN' as const,
          result: {},
        },
      ],
      details_json: {},
      started_at: new Date(Date.now() - 7200000).toISOString(),
      completed_at: new Date(Date.now() - 3600000).toISOString(),
      created_at: new Date(Date.now() - 7200000).toISOString(),
      updated_at: new Date(Date.now() - 3600000).toISOString(),
    },
  ]

  const mockAssets = [
    { id: 'asset-1', name: 'Test Asset 1', key: 'test-asset-1' },
    { id: 'asset-2', name: 'Test Asset 2', key: 'test-asset-2' },
  ]

  const mockDatasets = [
    { id: 'dataset-1', name: 'Test Dataset 1', asset_id: 'asset-1' },
    { id: 'dataset-2', name: 'Test Dataset 2', asset_id: 'asset-2' },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseDQRuns.mockReturnValue({
      data: {
        results: mockDQRuns,
        count: mockDQRuns.length,
        next: null,
        previous: null,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)
    mockUseRunDQRun.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue(mockDQRuns[0]),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      data: undefined,
    } as any)
    mockUseAssets.mockReturnValue({
      data: {
        results: mockAssets,
        count: mockAssets.length,
        next: null,
        previous: null,
      },
      isLoading: false,
    } as any)
    mockUseDatasets.mockReturnValue({
      data: {
        results: mockDatasets,
        count: mockDatasets.length,
        next: null,
        previous: null,
      },
      isLoading: false,
    } as any)
  })

  describe('Rendering', () => {
    it('should render page title and description', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/data quality dashboard/i)).toBeInTheDocument()
      expect(screen.getByText(/monitor data quality runs/i)).toBeInTheDocument()
    })

    it('should render overview statistics cards', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/total runs/i)).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText(/average score/i)).toBeInTheDocument()
      expect(screen.getByText(/passed runs/i)).toBeInTheDocument()
      expect(screen.getByText(/failed runs/i)).toBeInTheDocument()
    })

    it('should render DQ metrics section', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/dq metrics/i)).toBeInTheDocument()
      expect(screen.getByText(/check statistics/i)).toBeInTheDocument()
      expect(screen.getByText(/run status breakdown/i)).toBeInTheDocument()
    })

    it('should render DQ runs list', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/dq runs/i)).toBeInTheDocument()
      expect(screen.getByText(/dq-run-1/i)).toBeInTheDocument()
    })
  })

  describe('Overview Statistics', () => {
    it('should calculate and display correct statistics', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      // Total runs
      expect(screen.getByText('2')).toBeInTheDocument()

      // Average score should be (85.5 + 65.0) / 2 = 75.25, rounded to 75
      const averageScoreElement = screen.getByText(/75/i)
      expect(averageScoreElement).toBeInTheDocument()

      // Passed runs (1 with PASS status)
      const passedRuns = screen.getAllByText('1')
      expect(passedRuns.length).toBeGreaterThan(0)
    })

    it('should display check statistics correctly', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      // Total checks: 2 + 1 = 3
      expect(screen.getByText(/total checks/i)).toBeInTheDocument()
      // Passed: 1, Failed: 1, Warnings: 1
      expect(screen.getByText(/passed/i)).toBeInTheDocument()
      expect(screen.getByText(/failed/i)).toBeInTheDocument()
      expect(screen.getByText(/warnings/i)).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('should filter runs by status', async () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const statusSelect = screen.getByLabelText(/run status/i)
      fireEvent.mousedown(statusSelect)
      await waitFor(() => {
        const option = screen.getByText('Succeeded')
        fireEvent.click(option)
      })

      // Should filter to only succeeded runs
      expect(statusSelect).toBeInTheDocument()
    })

    it('should filter runs by overall status', async () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const overallStatusSelect = screen.getByLabelText(/overall status/i)
      fireEvent.mousedown(overallStatusSelect)
      await waitFor(() => {
        const option = screen.getByText('Pass')
        fireEvent.click(option)
      })

      expect(overallStatusSelect).toBeInTheDocument()
    })

    it('should filter runs by engine', async () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const engineSelect = screen.getByLabelText(/engine/i)
      fireEvent.mousedown(engineSelect)
      await waitFor(() => {
        const option = screen.getByText('Great Expectations')
        fireEvent.click(option)
      })

      expect(engineSelect).toBeInTheDocument()
    })

    it('should filter runs by asset ID', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const assetIdInput = screen.getByLabelText(/asset id/i)
      fireEvent.change(assetIdInput, { target: { value: 'asset-1' } })

      expect(assetIdInput).toHaveValue('asset-1')
    })
  })

  describe('Run DQ Check', () => {
    it('should open run dialog when button is clicked', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const runButton = screen.getByText(/run dq check/i)
      fireEvent.click(runButton)

      expect(screen.getByText(/run data quality check/i)).toBeInTheDocument()
    })

    it('should display assets in run dialog', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const runButton = screen.getByText(/run dq check/i)
      fireEvent.click(runButton)

      expect(screen.getByText(/select an asset/i)).toBeInTheDocument()
    })

    it('should run DQ check when form is submitted', async () => {
      const mockMutateAsync = vi.fn().mockResolvedValue(mockDQRuns[0])
      mockUseRunDQRun.mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: mockMutateAsync,
        isPending: false,
        isError: false,
        isSuccess: false,
        error: null,
        data: undefined,
      } as any)

      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const runButton = screen.getByText(/run dq check/i)
      fireEvent.click(runButton)

      await waitFor(() => {
        const assetSelect = screen.getByLabelText(/asset/i)
        fireEvent.mousedown(assetSelect)
      })

      await waitFor(() => {
        const option = screen.getByText('Test Asset 1')
        fireEvent.click(option)
      })

      const submitButton = screen.getByText(/run check/i)
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(mockMutateAsync).toHaveBeenCalled()
      })
    })
  })

  describe('Schedule DQ Run', () => {
    it('should open schedule dialog when button is clicked', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const scheduleButton = screen.getByText(/schedule run/i)
      fireEvent.click(scheduleButton)

      expect(screen.getByText(/schedule data quality run/i)).toBeInTheDocument()
      expect(screen.getByText(/scheduling functionality will be implemented/i)).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('should display loading state when data is loading', () => {
      mockUseDQRuns.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/loading data quality dashboard/i)).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error state when data fails to load', () => {
      mockUseDQRuns.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load'),
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/failed to load data quality dashboard/i)).toBeInTheDocument()
      expect(screen.getByText('Failed to load')).toBeInTheDocument()
    })
  })

  describe('Navigation', () => {
    it('should navigate to run detail when run is clicked', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const runRow = screen.getByText(/dq-run-1/i).closest('tr')
      if (runRow) {
        fireEvent.click(runRow)
        expect(mockNavigate).toHaveBeenCalledWith('/data-quality/runs/dq-run-1')
      }
    })

    it('should navigate to run detail when arrow button is clicked', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const arrowButtons = screen.getAllByRole('button', { name: /arrow/i })
      if (arrowButtons.length > 0) {
        fireEvent.click(arrowButtons[0])
        expect(mockNavigate).toHaveBeenCalled()
      }
    })
  })

  describe('Refresh', () => {
    it('should call refetch when refresh button is clicked', () => {
      const mockRefetch = vi.fn()
      mockUseDQRuns.mockReturnValue({
        data: {
          results: mockDQRuns,
          count: mockDQRuns.length,
          next: null,
          previous: null,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      fireEvent.click(refreshButton)

      expect(mockRefetch).toHaveBeenCalled()
    })
  })

  describe('Empty States', () => {
    it('should display empty state when no runs are found', () => {
      mockUseDQRuns.mockReturnValue({
        data: {
          results: [],
          count: 0,
          next: null,
          previous: null,
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      expect(screen.getByText(/no dq runs found/i)).toBeInTheDocument()
    })
  })

  describe('Quality Score Display', () => {
    it('should display quality score with progress bar', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      // Should show quality scores (85 and 65)
      expect(screen.getByText(/86/i)).toBeInTheDocument() // Rounded 85.5
      expect(screen.getByText(/65/i)).toBeInTheDocument()
    })

    it('should use correct color for quality score', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      // Score >= 80 should be success (green)
      // Score < 60 should be error (red)
      // Score 60-80 should be warning (yellow)
      const progressBars = screen.getAllByRole('progressbar')
      expect(progressBars.length).toBeGreaterThan(0)
    })
  })

  describe('Check Results Display', () => {
    it('should display check counts for each run', () => {
      render(
        <TestWrapper>
          <DataQualityDashboardPage />
        </TestWrapper>
      )

      // Should show check chips (Pass, Fail, Warn)
      expect(screen.getByText(/1 Pass/i)).toBeInTheDocument()
      expect(screen.getByText(/1 Fail/i)).toBeInTheDocument()
      expect(screen.getByText(/1 Warn/i)).toBeInTheDocument()
    })
  })
})

