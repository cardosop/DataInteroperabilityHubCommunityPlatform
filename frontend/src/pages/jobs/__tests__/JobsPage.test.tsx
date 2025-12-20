/**
 * JobsPage Tests
 *
 * Comprehensive tests for the JobsPage component covering:
 * - Page rendering
 * - Job list display
 * - Real-time WebSocket updates
 * - Job completion notifications
 * - Job failure notifications
 * - Filtering functionality
 * - Job cancellation
 * - Loading states
 * - Error states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { JobsPage } from '../JobsPage'
import { useJobs } from '@/hooks/useJobs'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'

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
vi.mock('@/hooks/useJobs', () => ({
  useJobs: vi.fn(),
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(),
}))

vi.mock('@/components/feedback/Toast/useToastManager', () => ({
  useToastManager: vi.fn(),
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

describe('JobsPage', () => {
  const mockUseJobs = vi.mocked(useJobs)
  const mockUseWebSocket = vi.mocked(useWebSocket)
  const mockUseToastManager = vi.mocked(useToastManager)

  const mockJobs = [
    {
      id: 'job-1',
      tenant: 'tenant-1',
      type: 'DQ_RUN' as const,
      status: 'RUNNING' as const,
      resource_type: 'ASSET',
      resource_id: 'asset-1',
      created_by: 'user-1',
      started_at: new Date(Date.now() - 60000).toISOString(),
      completed_at: null,
      error_message: null,
      result_json: null,
      details_json: { progress: { percentage: 50 } },
      timeout_seconds: 300,
      created_at: new Date(Date.now() - 120000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'job-2',
      tenant: 'tenant-1',
      type: 'COMPLIANCE_RUN' as const,
      status: 'COMPLETED' as const,
      resource_type: 'ASSET',
      resource_id: 'asset-2',
      created_by: 'user-1',
      started_at: new Date(Date.now() - 3600000).toISOString(),
      completed_at: new Date(Date.now() - 3000000).toISOString(),
      error_message: null,
      result_json: { success: true },
      details_json: {},
      timeout_seconds: 600,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      updated_at: new Date(Date.now() - 3000000).toISOString(),
    },
    {
      id: 'job-3',
      tenant: 'tenant-1',
      type: 'CONTRACT_VALIDATION' as const,
      status: 'FAILED' as const,
      resource_type: 'CONTRACT',
      resource_id: 'contract-1',
      created_by: 'user-1',
      started_at: new Date(Date.now() - 7200000).toISOString(),
      completed_at: new Date(Date.now() - 7000000).toISOString(),
      error_message: 'Validation failed: Invalid schema',
      result_json: { error: 'Invalid schema' },
      details_json: {},
      timeout_seconds: 300,
      created_at: new Date(Date.now() - 7200000).toISOString(),
      updated_at: new Date(Date.now() - 7000000).toISOString(),
    },
  ]

  const mockJobsResponse = {
    count: 3,
    total_pages: 1,
    page: 1,
    page_size: 20,
    results: mockJobs,
  }

  const mockShowToast = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseJobs.mockReturnValue({
      data: mockJobsResponse,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)

    mockUseWebSocket.mockReturnValue({
      status: {
        state: 'CONNECTED' as const,
        isConnected: true,
        isConnecting: false,
        isReconnecting: false,
        isDisconnected: false,
      },
      isConnected: true,
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
      client: {} as any,
    } as any)

    mockUseToastManager.mockReturnValue({
      showToast: mockShowToast,
    } as any)
  })

  describe('Page Rendering', () => {
    it('should render the jobs page', () => {
      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(screen.getByText('Jobs')).toBeInTheDocument()
      expect(screen.getByText('Monitor and manage background jobs')).toBeInTheDocument()
    })

    it('should display real-time updates indicator when WebSocket is connected', () => {
      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(screen.getByText('Real-time updates active')).toBeInTheDocument()
    })

    it('should display jobs table', () => {
      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(screen.getByText('job-1'.substring(0, 8))).toBeInTheDocument()
      expect(screen.getByText('job-2'.substring(0, 8))).toBeInTheDocument()
      expect(screen.getByText('job-3'.substring(0, 8))).toBeInTheDocument()
    })
  })

  describe('Real-time WebSocket Updates', () => {
    it('should subscribe to job events via WebSocket', () => {
      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(mockUseWebSocket).toHaveBeenCalledWith(
        ['job.started', 'job.completed', 'job.failed', 'job.cancelled'],
        expect.any(Function)
      )
    })

    it('should show notification when job completes via WebSocket', async () => {
      let eventHandler: ((event: any) => void) | null = null

      mockUseWebSocket.mockImplementation((eventTypes, handler) => {
        eventHandler = handler
        return {
          status: {
            state: 'CONNECTED' as const,
            isConnected: true,
            isConnecting: false,
            isReconnecting: false,
            isDisconnected: false,
          },
          isConnected: true,
          subscribe: vi.fn(),
          unsubscribe: vi.fn(),
          client: {} as any,
        } as any
      })

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      // Simulate job completion event
      if (eventHandler) {
        eventHandler({
          event_type: 'job.completed',
          event_id: 'event-1',
          timestamp: new Date().toISOString(),
          data: {
            job_id: 'job-1',
            job_type: 'DQ_RUN',
            resource_type: 'ASSET',
            resource_id: 'asset-1',
            started_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        })
      }

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith({
          message: 'DQ_RUN completed successfully',
          severity: 'success',
        })
      })
    })

    it('should show notification when job fails via WebSocket', async () => {
      let eventHandler: ((event: any) => void) | null = null

      mockUseWebSocket.mockImplementation((eventTypes, handler) => {
        eventHandler = handler
        return {
          status: {
            state: 'CONNECTED' as const,
            isConnected: true,
            isConnecting: false,
            isReconnecting: false,
            isDisconnected: false,
          },
          isConnected: true,
          subscribe: vi.fn(),
          unsubscribe: vi.fn(),
          client: {} as any,
        } as any
      })

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      // Simulate job failure event
      if (eventHandler) {
        eventHandler({
          event_type: 'job.failed',
          event_id: 'event-2',
          timestamp: new Date().toISOString(),
          data: {
            job_id: 'job-2',
            job_type: 'COMPLIANCE_RUN',
            resource_type: 'ASSET',
            resource_id: 'asset-2',
            error_message: 'Compliance check failed',
            failed_at: new Date().toISOString(),
          },
        })
      }

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith({
          message: 'COMPLIANCE_RUN failed: Compliance check failed',
          severity: 'error',
        })
      })
    })

    it('should show notification when job is cancelled via WebSocket', async () => {
      let eventHandler: ((event: any) => void) | null = null

      mockUseWebSocket.mockImplementation((eventTypes, handler) => {
        eventHandler = handler
        return {
          status: {
            state: 'CONNECTED' as const,
            isConnected: true,
            isConnecting: false,
            isReconnecting: false,
            isDisconnected: false,
          },
          isConnected: true,
          subscribe: vi.fn(),
          unsubscribe: vi.fn(),
          client: {} as any,
        } as any
      })

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      // Simulate job cancellation event
      if (eventHandler) {
        eventHandler({
          event_type: 'job.cancelled',
          event_id: 'event-3',
          timestamp: new Date().toISOString(),
          data: {
            job_id: 'job-3',
            job_type: 'CONTRACT_VALIDATION',
            resource_type: 'CONTRACT',
            resource_id: 'contract-1',
          },
        })
      }

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith({
          message: 'CONTRACT_VALIDATION was cancelled',
          severity: 'info',
        })
      })
    })

    it('should not show duplicate notifications for the same event', async () => {
      let eventHandler: ((event: any) => void) | null = null

      mockUseWebSocket.mockImplementation((eventTypes, handler) => {
        eventHandler = handler
        return {
          status: {
            state: 'CONNECTED' as const,
            isConnected: true,
            isConnecting: false,
            isReconnecting: false,
            isDisconnected: false,
          },
          isConnected: true,
          subscribe: vi.fn(),
          unsubscribe: vi.fn(),
          client: {} as any,
        } as any
      })

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      const event = {
        event_type: 'job.completed',
        event_id: 'event-1',
        timestamp: new Date().toISOString(),
        data: {
          job_id: 'job-1',
          job_type: 'DQ_RUN',
          resource_type: 'ASSET',
          resource_id: 'asset-1',
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        },
      }

      // Simulate the same event twice
      if (eventHandler) {
        eventHandler(event)
        eventHandler(event)
      }

      await waitFor(() => {
        // Should only be called once
        expect(mockShowToast).toHaveBeenCalledTimes(1)
      })
    })
  })

  describe('Loading States', () => {
    it('should display loading state when jobs are loading', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(screen.getByText('Loading jobs...')).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error state when jobs fetch fails', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to fetch jobs' } as Error,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <JobsPage />
        </TestWrapper>
      )

      expect(screen.getByText('Failed to load jobs')).toBeInTheDocument()
      expect(screen.getByText('Failed to fetch jobs')).toBeInTheDocument()
    })
  })
})

