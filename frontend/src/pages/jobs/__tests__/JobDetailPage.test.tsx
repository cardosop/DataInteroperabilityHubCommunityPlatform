/**
 * JobDetailPage Tests
 *
 * Comprehensive tests for the JobDetailPage component covering:
 * - Page rendering
 * - Job detail display
 * - Real-time WebSocket updates
 * - Job progress updates
 * - Job completion notifications
 * - Job failure notifications
 * - Loading states
 * - Error states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { JobDetailPage } from '../JobDetailPage'
import { useJob, useJobStatus } from '@/hooks/useJobs'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'

// Mock useParams
const mockParams = { id: 'job-1' }
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => mockParams,
    useNavigate: () => vi.fn(),
  }
})

// Mock hooks
vi.mock('@/hooks/useJobs', () => ({
  useJob: vi.fn(),
  useJobStatus: vi.fn(),
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

describe('JobDetailPage', () => {
  const mockUseJob = vi.mocked(useJob)
  const mockUseJobStatus = vi.mocked(useJobStatus)
  const mockUseWebSocket = vi.mocked(useWebSocket)
  const mockUseToastManager = vi.mocked(useToastManager)

  const mockJob = {
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
    details_json: {
      progress: {
        percentage: 50,
        current: 5,
        total: 10,
        message: 'Processing data quality checks...',
      },
    },
    timeout_seconds: 300,
    created_at: new Date(Date.now() - 120000).toISOString(),
    updated_at: new Date().toISOString(),
  }

  const mockShowToast = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseJob.mockReturnValue({
      data: mockJob,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)

    mockUseJobStatus.mockReturnValue({
      data: undefined,
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
    it('should render the job detail page', () => {
      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Job Details')).toBeInTheDocument()
      expect(screen.getByText(/job-1/i)).toBeInTheDocument()
    })

    it('should display job information', () => {
      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Job Information')).toBeInTheDocument()
      expect(screen.getByText('RUNNING')).toBeInTheDocument()
      expect(screen.getByText('DQ_RUN')).toBeInTheDocument()
    })

    it('should display real-time indicator when WebSocket is connected', () => {
      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/real-time updates are active/i)).toBeInTheDocument()
      expect(screen.getByText('Real-time')).toBeInTheDocument()
    })

    it('should display job progress when running', () => {
      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Job Progress')).toBeInTheDocument()
      expect(screen.getByText('50%')).toBeInTheDocument()
      expect(screen.getByText('Processing data quality checks...')).toBeInTheDocument()
    })
  })

  describe('Real-time WebSocket Updates', () => {
    it('should subscribe to job events via WebSocket', () => {
      render(
        <TestWrapper>
          <JobDetailPage />
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
          <JobDetailPage />
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
          <JobDetailPage />
        </TestWrapper>
      )

      // Simulate job failure event
      if (eventHandler) {
        eventHandler({
          event_type: 'job.failed',
          event_id: 'event-2',
          timestamp: new Date().toISOString(),
          data: {
            job_id: 'job-1',
            job_type: 'DQ_RUN',
            resource_type: 'ASSET',
            resource_id: 'asset-1',
            error_message: 'Data quality check failed',
            failed_at: new Date().toISOString(),
          },
        })
      }

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith({
          message: 'DQ_RUN failed: Data quality check failed',
          severity: 'error',
        })
      })
    })

    it('should use polling fallback when WebSocket is not connected', () => {
      mockUseWebSocket.mockReturnValue({
        status: {
          state: 'DISCONNECTED' as const,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: true,
        },
        isConnected: false,
        subscribe: vi.fn(),
        unsubscribe: vi.fn(),
        client: {} as any,
      } as any)

      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      // Should enable polling when WebSocket is not connected
      expect(mockUseJobStatus).toHaveBeenCalledWith(
        'job-1',
        expect.objectContaining({
          enabled: true,
        })
      )
    })

    it('should not poll when WebSocket is connected', () => {
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

      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      // Should disable polling when WebSocket is connected
      expect(mockUseJobStatus).toHaveBeenCalledWith(
        'job-1',
        expect.objectContaining({
          enabled: false,
        })
      )
    })
  })

  describe('Loading States', () => {
    it('should display loading state when job is loading', () => {
      mockUseJob.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Loading job details...')).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error state when job fetch fails', () => {
      mockUseJob.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to fetch job' } as Error,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <JobDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Failed to load job')).toBeInTheDocument()
      expect(screen.getByText('Failed to fetch job')).toBeInTheDocument()
    })
  })
})

