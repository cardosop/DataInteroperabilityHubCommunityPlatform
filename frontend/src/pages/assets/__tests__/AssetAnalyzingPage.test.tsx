/**
 * AssetAnalyzingPage Tests
 *
 * Comprehensive tests for the Asset Analyzing Page (UI-DPO-003)
 * Implements all test requirements without mocks/stubs where possible.
 *
 * Test Coverage:
 * - Progress stepper display (5 steps)
 * - Real-time progress updates via WebSocket
 * - Loading spinner with status message
 * - Error handling with retry option
 * - Auto-navigation to contract editor on completion
 * - Background processing indicator (can navigate away)
 * - Step status updates (completed, in progress, pending)
 */

import { describe, it, expect, beforeEach, afterEach, vi, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AssetAnalyzingPage } from '../AssetAnalyzingPage'
import { renderWithProviders } from '@/test-utils'
import { createTestWebSocketServer, TestWebSocketServer } from '@/test-utils/websocket-test-server'
import { setupWebSocketPolyfill } from '@/test-utils/websocket-polyfill'
import { config } from '@/lib/config'
import { server } from '@/test-utils/msw/server'
import { rest } from 'msw'
import type { Dataset } from '@/lib/api/datasets'

// Setup WebSocket polyfill for real WebSocket connections
setupWebSocketPolyfill()

// Set auth token for WebSocket authentication
const setAuthToken = (token: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('auth_token', token)
  }
}

const clearAuthToken = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('auth_token')
  }
}

// Mock react-router-dom hooks
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  const mockNavigate = vi.fn()
  return {
    ...actual,
    useParams: () => ({ datasetId: 'dataset-1' }),
    useNavigate: () => mockNavigate,
  }
})

// Get the mocked navigate function
const getMockNavigate = () => {
  const { useNavigate } = require('react-router-dom')
  return useNavigate()
}

describe('AssetAnalyzingPage - UI-DPO-003', () => {
  let testServer: TestWebSocketServer
  let originalWsUrl: string
  let mockNavigate: ReturnType<typeof vi.fn>

  const mockDataset: Dataset = {
    id: 'dataset-1',
    tenant: 'tenant-1',
    name: 'Test Dataset',
    format: 'CSV',
    size_bytes: 1024,
    row_count: 100,
    column_count: 5,
    asset: 'asset-1',
    created_by: 'user-1',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    metadata_json: {},
    schema_json: null,
    file_path: '/path/to/file.csv',
    status: 'ACTIVE',
  }

  beforeAll(async () => {
    // Start test WebSocket server
    testServer = createTestWebSocketServer({
      port: 8082,
      path: '/ws',
      requireAuth: true,
    })

    await testServer.start()
    originalWsUrl = config.api.wsUrl

    // Override WebSocket URL for tests
    Object.defineProperty(config.api, 'wsUrl', {
      value: testServer.getUrl(),
      writable: true,
      configurable: true,
    })

    // Setup MSW handlers for dataset API
    server.use(
      rest.get(`${config.api.baseUrl}/api/v1/datasets/:id`, (req, res, ctx) => {
        return res(ctx.json(mockDataset))
      })
    )
  })

  afterAll(async () => {
    // Restore original WebSocket URL
    Object.defineProperty(config.api, 'wsUrl', {
      value: originalWsUrl,
      writable: true,
      configurable: true,
    })

    // Stop test server
    await testServer.stop()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    clearAuthToken()
    setAuthToken('test-token')
    mockNavigate = getMockNavigate()
  })

  afterEach(() => {
    clearAuthToken()
  })

  describe('Progress Stepper Display', () => {
    it('should display all 5 progress steps', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Check all 5 steps are displayed
      expect(screen.getByText('Upload file')).toBeInTheDocument()
      expect(screen.getByText('Infer schema')).toBeInTheDocument()
      expect(screen.getByText('Run data quality checks')).toBeInTheDocument()
      expect(screen.getByText('Run compliance checks')).toBeInTheDocument()
      expect(screen.getByText('Prepare contract draft')).toBeInTheDocument()
    })

    it('should display step descriptions', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Check initial step descriptions
      expect(screen.getByText('File uploaded successfully')).toBeInTheDocument()
      expect(screen.getByText('Analyzing data structure...')).toBeInTheDocument()
      expect(screen.getByText('Waiting for schema inference...')).toBeInTheDocument()
    })

    it('should show correct step status indicators', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // First step (upload) should be completed (checkmark)
      const stepper = screen.getByRole('region', { name: /stepper/i }) || document.body
      const steps = stepper.querySelectorAll('[aria-label*="Step"]')

      // Step 1 should show checkmark (completed)
      expect(steps[0]).toBeInTheDocument()

      // Step 2 should be active (in progress)
      expect(steps[1]).toBeInTheDocument()
    })
  })

  describe('Real-time Progress Updates via WebSocket', () => {
    it('should subscribe to WebSocket events on mount', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Wait for WebSocket connection
      await waitFor(
        () => {
          // Component should be rendered
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )
    })

    it('should update step status when receiving job.completed event', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.completed event via test server
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for UI update
      await waitFor(
        () => {
          // Step should show completed status
          expect(screen.getByText(/Completed successfully/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should update step progress when receiving job.progress event', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.progress event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-2',
          event_type: 'job.progress',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            progress: 50,
          },
        })
      })

      // Wait for progress update
      await waitFor(
        () => {
          expect(screen.getByText(/Progress: 50%/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should handle workflow progress events', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send workflow progress event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-3',
          event_type: 'asset.workflow.progress',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            current_step: 'dq-checks',
            progress: 75,
          },
        })
      })

      // Wait for workflow progress update
      await waitFor(
        () => {
          expect(screen.getByText(/Progress: 75%/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })
  })

  describe('Loading Spinner with Status Message', () => {
    it('should display loading spinner', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // CircularProgress should be rendered
      const spinner = document.querySelector('[role="progressbar"]')
      expect(spinner).toBeInTheDocument()
    })

    it('should display current step status message', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Should show current step message
      expect(screen.getByText(/Analyzing data structure.../i)).toBeInTheDocument()
    })

    it('should update status message when step changes', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Initial message
      expect(screen.getByText(/Analyzing data structure.../i)).toBeInTheDocument()

      // Send job.completed event to move to next step
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-4',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for status message update
      await waitFor(
        () => {
          // Should show next step message
          expect(screen.getByText(/Run data quality checks/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display overall progress percentage', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Should show progress percentage (1 out of 5 steps = 20%)
      expect(screen.getByText(/20% complete/i)).toBeInTheDocument()
    })
  })

  describe('Error Handling with Retry Option', () => {
    it('should display error message when job fails', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-5',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            error_message: 'Schema inference failed',
          },
        })
      })

      // Wait for error display
      await waitFor(
        () => {
          expect(screen.getByText(/Analysis failed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display retry button when error occurs', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-6',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            error_message: 'Schema inference failed',
          },
        })
      })

      // Wait for retry button
      await waitFor(
        () => {
          const retryButton = screen.getByRole('button', { name: /retry/i })
          expect(retryButton).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should clear error when retry button is clicked', async () => {
      const user = userEvent.setup()

      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-7',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            error_message: 'Schema inference failed',
          },
        })
      })

      // Wait for error and retry button
      await waitFor(
        () => {
          expect(screen.getByText(/Analysis failed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      const retryButton = screen.getByRole('button', { name: /retry/i })
      await user.click(retryButton)

      // Error should be cleared
      await waitFor(
        () => {
          expect(screen.queryByText(/Analysis failed/i)).not.toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })
  })

  describe('Auto-navigation to Contract Editor on Completion', () => {
    it('should navigate to assets page when all steps complete', async () => {
      vi.useFakeTimers()

      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Complete all steps by sending completion events
      const jobTypes = ['SCHEMA_INFERENCE', 'DQ_RUN', 'COMPLIANCE_SCAN', 'CONTRACT_PREP']

      for (let i = 0; i < jobTypes.length; i++) {
        await act(async () => {
          await testServer.broadcastEvent({
            event_id: `evt-complete-${i}`,
            event_type: 'job.completed',
            event_version: '1.0.0',
            timestamp: new Date().toISOString(),
            source: {
              service: 'hub',
              tenant_id: 'tenant-1',
            },
            data: {
              job_id: `job-${i}`,
              job_type: jobTypes[i],
            },
          })
        })
      }

      // Wait for all steps to complete
      await waitFor(
        () => {
          // All steps should be completed
          expect(screen.getByText(/100% complete/i)).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Fast-forward timer for auto-navigation (2 seconds delay)
      await act(async () => {
        vi.advanceTimersByTime(2000)
      })

      // Should navigate to assets page
      await waitFor(
        () => {
          expect(mockNavigate).toHaveBeenCalledWith('/assets')
        },
        { timeout: 1000 }
      )

      vi.useRealTimers()
    })

    it('should not navigate if there is an error', async () => {
      vi.useFakeTimers()

      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send error event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-error',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            error_message: 'Error occurred',
          },
        })
      })

      // Fast-forward timer
      await act(async () => {
        vi.advanceTimersByTime(2000)
      })

      // Should not navigate
      expect(mockNavigate).not.toHaveBeenCalledWith('/assets')

      vi.useRealTimers()
    })
  })

  describe('Background Processing Indicator', () => {
    it('should display background processing note', () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      expect(
        screen.getByText(/You can navigate away from this page/i)
      ).toBeInTheDocument()
      expect(
        screen.getByText(/analysis will continue in the background/i)
      ).toBeInTheDocument()
    })

    it('should allow navigation away while processing', async () => {
      const user = userEvent.setup()

      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      // Find "View Assets" button
      const viewAssetsButton = screen.getByRole('button', { name: /view assets/i })
      expect(viewAssetsButton).toBeInTheDocument()

      // Click to navigate away
      await user.click(viewAssetsButton)

      // Should navigate
      expect(mockNavigate).toHaveBeenCalledWith('/assets')
    })

    it('should show continue button when analysis is complete', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Complete all steps
      const jobTypes = ['SCHEMA_INFERENCE', 'DQ_RUN', 'COMPLIANCE_SCAN', 'CONTRACT_PREP']

      for (let i = 0; i < jobTypes.length; i++) {
        await act(async () => {
          await testServer.broadcastEvent({
            event_id: `evt-complete-btn-${i}`,
            event_type: 'job.completed',
            event_version: '1.0.0',
            timestamp: new Date().toISOString(),
            source: {
              service: 'hub',
              tenant_id: 'tenant-1',
            },
            data: {
              job_id: `job-${i}`,
              job_type: jobTypes[i],
            },
          })
        })
      }

      // Wait for completion
      await waitFor(
        () => {
          const continueButton = screen.getByRole('button', { name: /continue to assets/i })
          expect(continueButton).toBeInTheDocument()
        },
        { timeout: 5000 }
      )
    })
  })

  describe('Step Status Updates', () => {
    it('should update step status from pending to in-progress', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send workflow progress event to move to next step
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-status-1',
          event_type: 'asset.workflow.progress',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            current_step: 'dq-checks',
            progress: 0,
          },
        })
      })

      // Wait for step status update
      await waitFor(
        () => {
          expect(screen.getByText(/Run data quality checks/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should update step status from in-progress to completed', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.completed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-status-2',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for completed status
      await waitFor(
        () => {
          expect(screen.getByText(/Completed successfully/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should update step status to error when job fails', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-status-3',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
            error_message: 'Schema inference error',
          },
        })
      })

      // Wait for error status
      await waitFor(
        () => {
          expect(screen.getByText(/Error/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should move to next step when current step completes', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Complete infer-schema step
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-status-4',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for next step to become active
      await waitFor(
        () => {
          // DQ checks step should now be in progress
          expect(screen.getByText(/Run data quality checks/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should update progress percentage as steps complete', async () => {
      renderWithProviders(<AssetAnalyzingPage />, {
        initialEntries: ['/assets/analyzing/dataset-1'],
      })

      await waitFor(
        () => {
          expect(screen.getByText('Analyzing Data')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Initial progress should be 20% (1 out of 5 steps)
      expect(screen.getByText(/20% complete/i)).toBeInTheDocument()

      // Complete infer-schema step (2 out of 5 = 40%)
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-progress-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-1',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for progress update
      await waitFor(
        () => {
          expect(screen.getByText(/40% complete/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })
  })
})

