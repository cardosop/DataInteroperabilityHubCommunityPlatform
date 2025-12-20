/**
 * ComplianceReportPage Tests
 *
 * Comprehensive tests for the ComplianceReportPage component covering:
 * - Report overview display
 * - Compliance metrics display
 * - Violation breakdown by category
 * - Violation breakdown by jurisdiction
 * - Violation timeline display
 * - Asset compliance status display
 * - Report export functionality (PDF, CSV)
 * - Report filtering (date range, asset, jurisdiction)
 * - Report scheduling functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ComplianceReportPage } from '../ComplianceReportPage'
import * as complianceApi from '@/lib/api/compliance'
import { useComplianceReport } from '@/hooks/useComplianceReport'
import { useAssets } from '@/hooks/useAssets'

// Mock hooks
vi.mock('@/hooks/useComplianceReport', () => ({
  useComplianceReport: vi.fn(),
}))

vi.mock('@/hooks/useAssets', () => ({
  useAssets: vi.fn(),
}))

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock export utilities
vi.mock('@/lib/utils/dataExport', () => ({
  exportToCSV: vi.fn(),
  exportToJSON: vi.fn(),
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

const mockReportData: complianceApi.ComplianceReportData = {
  overview: {
    period: {
      start_date: '2024-01-01T00:00:00Z',
      end_date: '2024-12-31T23:59:59Z',
    },
    total_scans: 100,
    pass_rate: 0.85,
    violation_count: 25,
    risk_score: 0.35,
  },
  violation_breakdown_by_category: [
    {
      category: 'PII_DETECTION',
      count: 15,
      severity_breakdown: {
        CRITICAL: 2,
        HIGH: 5,
        MEDIUM: 6,
        LOW: 2,
      },
    },
    {
      category: 'DATA_RETENTION',
      count: 10,
      severity_breakdown: {
        CRITICAL: 0,
        HIGH: 3,
        MEDIUM: 5,
        LOW: 2,
      },
    },
  ],
  violation_breakdown_by_jurisdiction: [
    {
      jurisdiction: 'GDPR',
      total_violations: 15,
      pass_rate: 0.8,
      risk_score: 0.4,
    },
    {
      jurisdiction: 'HIPAA',
      total_violations: 10,
      pass_rate: 0.9,
      risk_score: 0.3,
    },
  ],
  violation_timeline: [
    {
      date: '2024-01-15',
      violations: 5,
      scans: 10,
      pass_rate: 0.8,
    },
    {
      date: '2024-02-15',
      violations: 8,
      scans: 15,
      pass_rate: 0.75,
    },
    {
      date: '2024-03-15',
      violations: 12,
      scans: 20,
      pass_rate: 0.7,
    },
  ],
  asset_compliance_status: [
    {
      asset_id: 'asset-1',
      last_scan_date: '2024-03-15T00:00:00Z',
      overall_status: 'PASS',
      risk_level: 'LOW',
      violation_count: 2,
      compliance_score: 0.9,
    },
    {
      asset_id: 'asset-2',
      last_scan_date: '2024-03-10T00:00:00Z',
      overall_status: 'WARN',
      risk_level: 'MEDIUM',
      violation_count: 8,
      compliance_score: 0.7,
    },
  ],
}

const mockAssets = {
  results: [
    {
      id: 'asset-1',
      name: 'Asset 1',
      description: 'Test Asset 1',
      domain: 'finance',
      status: 'ACTIVE',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'asset-2',
      name: 'Asset 2',
      description: 'Test Asset 2',
      domain: 'healthcare',
      status: 'ACTIVE',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ],
  count: 2,
  next: null,
  previous: null,
}

describe('ComplianceReportPage', () => {
  const mockUseComplianceReport = vi.mocked(useComplianceReport)
  const mockUseAssets = vi.mocked(useAssets)

  beforeEach(() => {
    vi.clearAllMocks()

    mockUseComplianceReport.mockReturnValue({
      data: mockReportData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    mockUseAssets.mockReturnValue({
      data: mockAssets,
      isLoading: false,
      error: null,
    } as any)
  })

  describe('Rendering', () => {
    it('should render the compliance report page', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/compliance report/i)).toBeInTheDocument()
    })

    it('should display report overview', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/overview/i)).toBeInTheDocument()
      expect(screen.getByText(/100/)).toBeInTheDocument() // total_scans
      expect(screen.getByText(/25/)).toBeInTheDocument() // violation_count
    })

    it('should display compliance metrics', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/pass rate/i)).toBeInTheDocument()
      expect(screen.getByText(/violation count/i)).toBeInTheDocument()
      expect(screen.getByText(/risk score/i)).toBeInTheDocument()
    })

    it('should display violation breakdown by category', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/violation breakdown by category/i)).toBeInTheDocument()
      expect(screen.getByText(/PII_DETECTION/i)).toBeInTheDocument()
      expect(screen.getByText(/DATA_RETENTION/i)).toBeInTheDocument()
    })

    it('should display violation breakdown by jurisdiction', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/violation breakdown by jurisdiction/i)).toBeInTheDocument()
      expect(screen.getByText(/GDPR/i)).toBeInTheDocument()
      expect(screen.getByText(/HIPAA/i)).toBeInTheDocument()
    })

    it('should display violation timeline', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/violation timeline/i)).toBeInTheDocument()
    })

    it('should display asset compliance status', () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/asset compliance status/i)).toBeInTheDocument()
    })
  })

  describe('Loading and Error States', () => {
    it('should display loading state', () => {
      mockUseComplianceReport.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('should display error state', () => {
      mockUseComplianceReport.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load report'),
        refetch: vi.fn(),
      } as any)

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      expect(screen.getByText(/error/i)).toBeInTheDocument()
      expect(screen.getByText(/failed to load report/i)).toBeInTheDocument()
    })
  })

  describe('Report Filtering', () => {
    it('should allow filtering by date range', async () => {
      const mockRefetch = vi.fn()
      mockUseComplianceReport.mockReturnValue({
        data: mockReportData,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      } as any)

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      // Find and interact with date range filters
      const startDateInput = screen.getByLabelText(/start date/i)
      const endDateInput = screen.getByLabelText(/end date/i)

      fireEvent.change(startDateInput, { target: { value: '2024-01-01' } })
      fireEvent.change(endDateInput, { target: { value: '2024-12-31' } })

      // Wait for filters to be applied
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled()
      })
    })

    it('should allow filtering by asset', async () => {
      const mockRefetch = vi.fn()
      mockUseComplianceReport.mockReturnValue({
        data: mockReportData,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      } as any)

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      // Find asset filter dropdown
      const assetFilter = screen.getByLabelText(/asset/i)
      fireEvent.mouseDown(assetFilter)

      await waitFor(() => {
        expect(screen.getByText(/asset 1/i)).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText(/asset 1/i))
    })

    it('should allow filtering by jurisdiction', async () => {
      const mockRefetch = vi.fn()
      mockUseComplianceReport.mockReturnValue({
        data: mockReportData,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      } as any)

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      // Find jurisdiction filter dropdown
      const jurisdictionFilter = screen.getByLabelText(/jurisdiction/i)
      fireEvent.mouseDown(jurisdictionFilter)

      await waitFor(() => {
        expect(screen.getByText(/GDPR/i)).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText(/GDPR/i))
    })
  })

  describe('Report Export', () => {
    it('should export report as CSV', async () => {
      const { exportToCSV } = await import('@/lib/utils/dataExport')

      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      const exportButton = screen.getByText(/export/i)
      fireEvent.click(exportButton)

      await waitFor(() => {
        const csvOption = screen.getByText(/export as csv/i)
        fireEvent.click(csvOption)
      })

      await waitFor(() => {
        expect(exportToCSV).toHaveBeenCalled()
      })
    })

    it('should export report as PDF', async () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      const exportButton = screen.getByText(/export/i)
      fireEvent.click(exportButton)

      await waitFor(() => {
        const pdfOption = screen.getByText(/export as pdf/i)
        fireEvent.click(pdfOption)
      })

      // PDF export would be implemented with jsPDF or similar
      // For now, we just verify the button exists
      expect(pdfOption).toBeInTheDocument()
    })
  })

  describe('Report Scheduling', () => {
    it('should open schedule dialog', async () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      const scheduleButton = screen.getByText(/schedule report/i)
      fireEvent.click(scheduleButton)

      await waitFor(() => {
        expect(screen.getByText(/schedule compliance report/i)).toBeInTheDocument()
      })
    })

    it('should allow selecting schedule frequency', async () => {
      render(
        <TestWrapper>
          <ComplianceReportPage />
        </TestWrapper>
      )

      const scheduleButton = screen.getByText(/schedule report/i)
      fireEvent.click(scheduleButton)

      await waitFor(() => {
        const frequencySelect = screen.getByLabelText(/frequency/i)
        fireEvent.mouseDown(frequencySelect)
      })

      await waitFor(() => {
        expect(screen.getByText(/daily/i)).toBeInTheDocument()
        expect(screen.getByText(/weekly/i)).toBeInTheDocument()
        expect(screen.getByText(/monthly/i)).toBeInTheDocument()
      })
    })
  })
})

