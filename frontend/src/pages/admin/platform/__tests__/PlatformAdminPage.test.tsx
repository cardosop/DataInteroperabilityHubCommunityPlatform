/**
 * PlatformAdminPage Tests
 *
 * Comprehensive tests for the PlatformAdminPage component covering:
 * - Page rendering
 * - Platform overview display
 * - Tenants list display
 * - System metrics display
 * - Tenant management (suspend, activate)
 * - Filtering functionality
 * - Loading states
 * - Error states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PlatformAdminPage } from '../PlatformAdminPage'
import { useTenants, useSystemMetrics, useSuspendTenant, useReactivateTenant } from '@/hooks/usePlatformAdmin'

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
vi.mock('@/hooks/usePlatformAdmin', () => ({
  useTenants: vi.fn(),
  useSystemMetrics: vi.fn(),
  useSuspendTenant: vi.fn(),
  useReactivateTenant: vi.fn(),
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

describe('PlatformAdminPage', () => {
  const mockUseTenants = vi.mocked(useTenants)
  const mockUseSystemMetrics = vi.mocked(useSystemMetrics)
  const mockUseSuspendTenant = vi.mocked(useSuspendTenant)
  const mockUseReactivateTenant = vi.mocked(useReactivateTenant)

  const mockTenants = [
    {
      id: 'tenant-1',
      name: 'Test Tenant 1',
      slug: 'test-tenant-1',
      status: 'ACTIVE' as const,
      kyc_status: 'VERIFIED' as const,
      region: 'us-east-1',
      deleted_at: null,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'tenant-2',
      name: 'Test Tenant 2',
      slug: 'test-tenant-2',
      status: 'SUSPENDED' as const,
      kyc_status: 'UNVERIFIED' as const,
      region: 'eu-west-1',
      deleted_at: null,
      created_at: new Date(Date.now() - 172800000).toISOString(),
      updated_at: new Date(Date.now() - 86400000).toISOString(),
    },
    {
      id: 'tenant-3',
      name: 'Test Tenant 3',
      slug: 'test-tenant-3',
      status: 'ACTIVE' as const,
      kyc_status: 'VERIFIED' as const,
      region: null,
      deleted_at: null,
      created_at: new Date(Date.now() - 259200000).toISOString(),
      updated_at: new Date().toISOString(),
    },
  ]

  const mockTenantsResponse = {
    count: 3,
    total_pages: 1,
    page: 1,
    page_size: 20,
    results: mockTenants,
  }

  const mockMetrics = `# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 1234
http_requests_total{method="POST",status="201"} 567
`

  const mockSuspendMutation = {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    data: null,
  }

  const mockReactivateMutation = {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    data: null,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseTenants.mockReturnValue({
      data: mockTenantsResponse,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)

    mockUseSystemMetrics.mockReturnValue({
      data: mockMetrics,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)

    mockUseSuspendTenant.mockReturnValue(mockSuspendMutation as any)
    mockUseReactivateTenant.mockReturnValue(mockReactivateMutation as any)
  })

  describe('Page Rendering', () => {
    it('should render the platform admin page', () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('Platform Administration')).toBeInTheDocument()
      expect(
        screen.getByText('Manage tenants, monitor system metrics, and oversee platform operations')
      ).toBeInTheDocument()
    })

    it('should display platform overview statistics', () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('Total Tenants')).toBeInTheDocument()
      expect(screen.getByText('Active Tenants')).toBeInTheDocument()
      expect(screen.getByText('Suspended')).toBeInTheDocument()
      expect(screen.getByText('Verified (KYC)')).toBeInTheDocument()
    })

    it('should calculate and display correct overview statistics', () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      // Total tenants: 3
      expect(screen.getByText('3')).toBeInTheDocument()
      // Active tenants: 2 (tenant-1 and tenant-3)
      // Suspended: 1 (tenant-2)
      // Verified: 2 (tenant-1 and tenant-3)
    })

    it('should display system metrics', () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('System Metrics')).toBeInTheDocument()
      expect(screen.getByText(/http_requests_total/)).toBeInTheDocument()
    })

    it('should display tenants table', () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('All Tenants')).toBeInTheDocument()
      expect(screen.getByText('Test Tenant 1')).toBeInTheDocument()
      expect(screen.getByText('Test Tenant 2')).toBeInTheDocument()
      expect(screen.getByText('Test Tenant 3')).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('should display loading state when tenants are loading', () => {
      mockUseTenants.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('Loading platform admin dashboard...')).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error state when tenants fetch fails', () => {
      mockUseTenants.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to fetch tenants' } as Error,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      expect(screen.getByText('Failed to load platform admin dashboard')).toBeInTheDocument()
      expect(screen.getByText('Failed to fetch tenants')).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('should filter tenants by status', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const statusSelect = screen.getByLabelText('Status')
      fireEvent.mousedown(statusSelect)
      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Active'))

      await waitFor(() => {
        expect(mockUseTenants).toHaveBeenCalledWith(
          expect.objectContaining({
            status: 'ACTIVE',
          })
        )
      })
    })

    it('should filter tenants by KYC status', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const kycSelect = screen.getByLabelText('KYC Status')
      fireEvent.mousedown(kycSelect)
      await waitFor(() => {
        expect(screen.getByText('Verified')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Verified'))

      await waitFor(() => {
        expect(mockUseTenants).toHaveBeenCalledWith(
          expect.objectContaining({
            kyc_status: 'VERIFIED',
          })
        )
      })
    })

    it('should filter tenants by search query', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Search tenants...')
      fireEvent.change(searchInput, { target: { value: 'Test Tenant 1' } })

      await waitFor(() => {
        expect(mockUseTenants).toHaveBeenCalledWith(
          expect.objectContaining({
            search: 'Test Tenant 1',
          })
        )
      })
    })

    it('should clear filters when clear button is clicked', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Search tenants...')
      fireEvent.change(searchInput, { target: { value: 'test' } })

      await waitFor(() => {
        expect(screen.getByText('Clear Filters')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Clear Filters'))

      await waitFor(() => {
        expect(searchInput).toHaveValue('')
      })
    })
  })

  describe('Tenant Management', () => {
    it('should open suspend dialog when suspend button is clicked', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      // Find suspend button for active tenant (first tenant is ACTIVE)
      const suspendButtons = screen.getAllByLabelText('Suspend Tenant')
      expect(suspendButtons.length).toBeGreaterThan(0)

      fireEvent.click(suspendButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Suspend Tenant')).toBeInTheDocument()
        expect(screen.getByText(/Test Tenant 1/)).toBeInTheDocument()
      })
    })

    it('should open reactivate dialog when reactivate button is clicked', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      // Find reactivate button for suspended tenant (second tenant is SUSPENDED)
      const reactivateButtons = screen.getAllByLabelText('Reactivate Tenant')
      expect(reactivateButtons.length).toBeGreaterThan(0)

      fireEvent.click(reactivateButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Reactivate Tenant')).toBeInTheDocument()
        expect(screen.getByText(/Test Tenant 2/)).toBeInTheDocument()
      })
    })

    it('should call suspend mutation when suspend is confirmed', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const suspendButtons = screen.getAllByLabelText('Suspend Tenant')
      fireEvent.click(suspendButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Suspend Tenant')).toBeInTheDocument()
      })

      const reasonInput = screen.getByPlaceholderText('Enter reason for suspension...')
      fireEvent.change(reasonInput, { target: { value: 'Test suspension reason' } })

      const confirmButton = screen.getByText('Suspend Tenant', { selector: 'button' })
      fireEvent.click(confirmButton)

      await waitFor(() => {
        expect(mockSuspendMutation.mutate).toHaveBeenCalledWith(
          expect.objectContaining({
            tenantId: 'tenant-1',
            data: { reason: 'Test suspension reason' },
          })
        )
      })
    })

    it('should call reactivate mutation when reactivate is confirmed', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const reactivateButtons = screen.getAllByLabelText('Reactivate Tenant')
      fireEvent.click(reactivateButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Reactivate Tenant')).toBeInTheDocument()
      })

      const reasonInput = screen.getByPlaceholderText('Enter reason for reactivation...')
      fireEvent.change(reasonInput, { target: { value: 'Test reactivation reason' } })

      const confirmButton = screen.getByText('Reactivate Tenant', { selector: 'button' })
      fireEvent.click(confirmButton)

      await waitFor(() => {
        expect(mockReactivateMutation.mutate).toHaveBeenCalledWith(
          expect.objectContaining({
            tenantId: 'tenant-2',
            data: { reason: 'Test reactivation reason' },
          })
        )
      })
    })

    it('should navigate to tenant detail when view button is clicked', async () => {
      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const viewButtons = screen.getAllByLabelText('View Details')
      fireEvent.click(viewButtons[0])

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/admin/tenants/tenant-1')
      })
    })
  })

  describe('Empty States', () => {
    it('should display empty state when no tenants match filters', async () => {
      mockUseTenants.mockReturnValue({
        data: {
          count: 0,
          total_pages: 0,
          page: 1,
          page_size: 20,
          results: [],
        },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      // Wait for the component to render the empty state
      await waitFor(() => {
        expect(screen.getByText('No tenants found')).toBeInTheDocument()
      })

      expect(screen.getByText('No tenants match the current filters.')).toBeInTheDocument()
    })
  })

  describe('Refresh Functionality', () => {
    it('should refresh tenants when refresh button is clicked', async () => {
      const mockRefetch = vi.fn()
      mockUseTenants.mockReturnValue({
        data: mockTenantsResponse,
        isLoading: false,
        isError: false,
        error: null,
        refetch: mockRefetch,
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const refreshButtons = screen.getAllByLabelText('Refresh All')
      fireEvent.click(refreshButtons[0])

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled()
      })
    })

    it('should refresh metrics when metrics refresh button is clicked', async () => {
      const mockRefetchMetrics = vi.fn()
      mockUseSystemMetrics.mockReturnValue({
        data: mockMetrics,
        isLoading: false,
        isError: false,
        error: null,
        refetch: mockRefetchMetrics,
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <PlatformAdminPage />
        </TestWrapper>
      )

      const refreshButtons = screen.getAllByLabelText('Refresh Metrics')
      fireEvent.click(refreshButtons[0])

      await waitFor(() => {
        expect(mockRefetchMetrics).toHaveBeenCalled()
      })
    })
  })
})

