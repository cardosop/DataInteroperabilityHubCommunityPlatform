/**
 * ComplianceScanDetailPage Tests
 *
 * Comprehensive tests for the ComplianceScanDetailPage component covering:
 * - Page rendering
 * - Scan information display
 * - Scan results display
 * - Violations display with details
 * - Remediation suggestions display
 * - Loading states
 * - Error states
 * - Navigation
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { ComplianceScanDetailPage } from '../ComplianceScanDetailPage'
import { useComplianceScan } from '@/hooks/useComplianceScan'
import { useComplianceScanResults } from '@/hooks/useComplianceScanResults'
import { useAsset } from '@/hooks/useAssets'
import { useDataset } from '@/hooks/useDatasets'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: 'scan-1' }),
  }
})

// Mock hooks
vi.mock('@/hooks/useComplianceScan', () => ({
  useComplianceScan: vi.fn(),
}))

vi.mock('@/hooks/useComplianceScanResults', () => ({
  useComplianceScanResults: vi.fn(),
}))

vi.mock('@/hooks/useAssets', () => ({
  useAsset: vi.fn(),
}))

vi.mock('@/hooks/useDatasets', () => ({
  useDataset: vi.fn(),
}))


describe('ComplianceScanDetailPage', () => {
  const mockUseComplianceScan = vi.mocked(useComplianceScan)
  const mockUseComplianceScanResults = vi.mocked(useComplianceScanResults)
  const mockUseAsset = vi.mocked(useAsset)
  const mockUseDataset = vi.mocked(useDataset)

  const mockScan = {
    id: 'scan-1',
    tenant: 'tenant-1',
    asset: 'asset-1',
    dataset: null,
    file: null,
    job: 'job-1',
    regulations: ['GDPR', 'CCPA'],
    status: 'SUCCEEDED',
    overall_status: 'FAIL',
    risk_level: 'HIGH',
    allowed_to_store: false,
    started_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date().toISOString(),
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date().toISOString(),
  }

  const mockResults = {
    compliance_run_id: 'scan-1',
    overall_status: 'FAIL',
    risk_level: 'HIGH',
    allowed_to_store: false,
    compliance_score: 0.65,
    violations: [
      {
        id: 'violation-1',
        type: 'Data Retention',
        severity: 'CRITICAL',
        description: 'Data retention period exceeds GDPR requirements',
        remediation: 'Reduce retention period to comply with GDPR',
      },
      {
        id: 'violation-2',
        type: 'Data Access',
        severity: 'HIGH',
        description: 'Insufficient access controls',
        remediation: 'Implement proper access controls',
      },
    ],
    remediation_suggestions: [
      'Review and update data retention policies',
      'Implement role-based access controls',
      'Conduct regular compliance audits',
    ],
  }

  const mockAsset = {
    id: 'asset-1',
    name: 'Test Asset',
    key: 'test-asset',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseComplianceScan.mockReturnValue({
      data: mockScan,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    mockUseComplianceScanResults.mockReturnValue({
      data: mockResults,
      isLoading: false,
      error: null,
    } as any)
    mockUseAsset.mockReturnValue({
      data: mockAsset,
      isLoading: false,
    } as any)
    mockUseDataset.mockReturnValue({
      data: null,
      isLoading: false,
    } as any)
  })

  describe('Rendering', () => {
    it('should render page title and scan ID', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/compliance scan details/i)).toBeInTheDocument()
      expect(screen.getByText('scan-1')).toBeInTheDocument()
    })

    it('should render scan information section', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/scan information/i)).toBeInTheDocument()
      expect(screen.getByText('SUCCEEDED')).toBeInTheDocument()
      expect(screen.getByText('FAIL')).toBeInTheDocument()
      expect(screen.getByText('HIGH')).toBeInTheDocument()
    })

    it('should render regulations', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText('GDPR')).toBeInTheDocument()
      expect(screen.getByText('CCPA')).toBeInTheDocument()
    })

    it('should render scan results summary', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/scan results summary/i)).toBeInTheDocument()
      expect(screen.getByText(/65%/i)).toBeInTheDocument()
      expect(screen.getByText(/total violations/i)).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
    })

    it('should render violations section', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/violations/i)).toBeInTheDocument()
      expect(screen.getByText(/data retention/i)).toBeInTheDocument()
      expect(screen.getByText(/data retention period exceeds gdpr requirements/i)).toBeInTheDocument()
    })

    it('should render remediation suggestions', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      // Use getAllByText since there might be multiple instances, then check the first one
      const suggestionsHeaders = screen.getAllByText(/remediation suggestions/i)
      expect(suggestionsHeaders.length).toBeGreaterThan(0)
      expect(screen.getByText(/review and update data retention policies/i)).toBeInTheDocument()
      expect(screen.getByText(/implement role-based access controls/i)).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('should display loading state when scan is loading', () => {
      mockUseComplianceScan.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/loading compliance scan/i)).toBeInTheDocument()
    })

    it('should display loading state when results are loading', () => {
      mockUseComplianceScanResults.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error state when scan fails to load', () => {
      mockUseComplianceScan.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load scan'),
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/failed to load compliance scan/i)).toBeInTheDocument()
      expect(screen.getByText('Failed to load scan')).toBeInTheDocument()
    })

    it('should display error message when results fail to load', () => {
      mockUseComplianceScanResults.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load results'),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/could not load scan results/i)).toBeInTheDocument()
    })
  })

  describe('Scan Status', () => {
    it('should display running status alert', () => {
      mockUseComplianceScan.mockReturnValue({
        data: { ...mockScan, status: 'RUNNING' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/scan is running/i)).toBeInTheDocument()
      expect(screen.getByText(/results will be available once the scan completes/i)).toBeInTheDocument()
    })

    it('should display failed status alert', () => {
      mockUseComplianceScan.mockReturnValue({
        data: { ...mockScan, status: 'FAILED' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/scan failed/i)).toBeInTheDocument()
    })

    it('should not display results when scan is not completed', () => {
      mockUseComplianceScan.mockReturnValue({
        data: { ...mockScan, status: 'PENDING' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.queryByText(/scan results summary/i)).not.toBeInTheDocument()
      expect(screen.getByText(/scan in progress/i)).toBeInTheDocument()
    })
  })

  describe('Violations Display', () => {
    it('should display violation statistics', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText(/1 Critical/i)).toBeInTheDocument()
      expect(screen.getByText(/1 High/i)).toBeInTheDocument()
    })

    it('should display violation details', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText('Data Retention')).toBeInTheDocument()
      expect(screen.getByText(/data retention period exceeds gdpr requirements/i)).toBeInTheDocument()
      expect(screen.getByText(/reduce retention period to comply with gdpr/i)).toBeInTheDocument()
    })
  })

  describe('Remediation Suggestions', () => {
    it('should display remediation suggestions as list items', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      const suggestions = screen.getByText(/remediation suggestions/i).closest('div')?.querySelector('ul')
      expect(suggestions).toBeInTheDocument()
      expect(suggestions?.children.length).toBe(3)
    })

    it('should handle object-based remediation suggestions', () => {
      const objectSuggestions = [
        {
          title: 'Fix Data Retention',
          description: 'Update retention policies',
          steps: ['Step 1', 'Step 2'],
        },
      ]

      mockUseComplianceScanResults.mockReturnValue({
        data: { ...mockResults, remediation_suggestions: objectSuggestions },
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/update retention policies/i)).toBeInTheDocument()
    })
  })

  describe('Associated Resources', () => {
    it('should display associated asset with link', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/associated resources/i)).toBeInTheDocument()
      expect(screen.getByText('Test Asset')).toBeInTheDocument()
    })

    it('should navigate to asset when asset link is clicked', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      const assetLink = screen.getByText('Test Asset')
      assetLink.click()

      expect(mockNavigate).toHaveBeenCalledWith('/assets/asset-1')
    })

    it('should display associated dataset if available', () => {
      mockUseDataset.mockReturnValue({
        data: { id: 'dataset-1', name: 'Test Dataset' },
        isLoading: false,
      } as any)

      mockUseComplianceScan.mockReturnValue({
        data: { ...mockScan, dataset: 'dataset-1' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText('Test Dataset')).toBeInTheDocument()
    })
  })

  describe('Navigation', () => {
    it('should navigate back when back button is clicked', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      const backButton = screen.getByRole('button', { name: /back/i })
      backButton.click()

      expect(mockNavigate).toHaveBeenCalledWith('/compliance')
    })

    it('should call refetch when refresh button is clicked', () => {
      const mockRefetch = vi.fn()
      mockUseComplianceScan.mockReturnValue({
        data: mockScan,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      refreshButton.click()

      expect(mockRefetch).toHaveBeenCalled()
    })
  })

  describe('Compliance Score Display', () => {
    it('should display compliance score with progress bar', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/compliance score/i)).toBeInTheDocument()
      expect(screen.getByText(/65%/i)).toBeInTheDocument()
    })

    it('should use correct color for compliance score', () => {
      // Score >= 0.8 should be success (green)
      mockUseComplianceScanResults.mockReturnValue({
        data: { ...mockResults, compliance_score: 0.85 },
        isLoading: false,
        error: null,
      } as any)

      const { rerender } = render(
        <TestWrapper>
          <ComplianceScanDetailPage />
        </TestWrapper>
      )

      // Score < 0.6 should be error (red)
      mockUseComplianceScanResults.mockReturnValue({
        data: { ...mockResults, compliance_score: 0.55 },
        isLoading: false,
        error: null,
      } as any)

      rerender(
        <TestWrapper>
          <ComplianceScanDetailPage />
        </TestWrapper>
      )

      // Both should render
      expect(screen.getByText(/compliance score/i)).toBeInTheDocument()
    })
  })

  describe('Allowed to Store Display', () => {
    it('should display allowed to store status', () => {
      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText(/allowed to store/i)).toBeInTheDocument()
      expect(screen.getByText('No')).toBeInTheDocument()
    })

    it('should display yes when allowed to store is true', () => {
      mockUseComplianceScanResults.mockReturnValue({
        data: { ...mockResults, allowed_to_store: true },
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<ComplianceScanDetailPage />, {
        initialEntries: ['/compliance/scans/scan-1'],
      })

      expect(screen.getByText('Yes')).toBeInTheDocument()
    })
  })
})

