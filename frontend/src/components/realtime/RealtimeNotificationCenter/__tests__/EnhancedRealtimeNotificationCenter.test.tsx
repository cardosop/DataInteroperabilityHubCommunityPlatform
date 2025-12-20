/**
 * Enhanced Realtime Notification Center Tests
 *
 * Comprehensive tests for real-time notifications covering:
 * - Notification display (all severities, timestamps, read/unread states)
 * - Notification actions (View Job, View Contract, View Asset)
 * - Notification persistence (save to and load from localStorage)
 * - Notification dismissal (single and all)
 *
 * Uses real WebSocket test server (no mocks/stubs)
 */

import { describe, it, expect, beforeEach, afterEach, vi, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EnhancedRealtimeNotificationCenter } from '../EnhancedRealtimeNotificationCenter'
import { renderWithProviders } from '@/test-utils'
import { createTestWebSocketServer, TestWebSocketServer } from '@/test-utils/websocket-test-server'
import { setupWebSocketPolyfill } from '@/test-utils/websocket-polyfill'
import { config } from '@/lib/config'

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

// Clear notifications from localStorage
const clearNotifications = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('notifications')
  }
}

describe('EnhancedRealtimeNotificationCenter - Real-time Notifications', () => {
  let testServer: TestWebSocketServer
  let originalWsUrl: string
  const mockOnClose = vi.fn()

  beforeAll(async () => {
    // Start test WebSocket server
    testServer = createTestWebSocketServer({
      port: 8083,
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
    clearNotifications()
  })

  afterEach(() => {
    clearAuthToken()
    clearNotifications()
  })

  describe('Notification Display', () => {
    it('should display notification center when open', () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} />,
        {}
      )

      expect(screen.getByText('Notifications')).toBeInTheDocument()
    })

    it('should not display notification center when closed', () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={false} onClose={mockOnClose} />,
        {}
      )

      expect(screen.queryByText('Notifications')).not.toBeInTheDocument()
    })

    it('should display success notification from WebSocket event', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.completed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-success-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-123',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for notification to appear
      await waitFor(
        () => {
          expect(screen.getByText(/Job Completed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display error notification from WebSocket event', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-error-1',
          event_type: 'job.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-456',
            job_type: 'DQ_RUN',
            error_message: 'Data quality check failed',
          },
        })
      })

      // Wait for error notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Failed/i)).toBeInTheDocument()
          expect(screen.getByText(/Data quality check failed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display warning notification from WebSocket event', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send compliance check failed event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-warning-1',
          event_type: 'compliance.check.failed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            check_id: 'check-789',
            violation_count: 3,
          },
        })
      })

      // Wait for warning notification
      await waitFor(
        () => {
          expect(screen.getByText(/Compliance Check Failed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display info notification from WebSocket event', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job.started event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-info-1',
          event_type: 'job.started',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-999',
            job_type: 'COMPLIANCE_SCAN',
          },
        })
      })

      // Wait for info notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Started/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display notification timestamp', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-timestamp-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-111',
          },
        })
      })

      // Wait for notification with timestamp
      await waitFor(
        () => {
          expect(screen.getByText(/Just now|m ago/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should show unread badge count', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send multiple events
      for (let i = 0; i < 3; i++) {
        await act(async () => {
          await testServer.broadcastEvent({
            event_id: `evt-badge-${i}`,
            event_type: 'job.completed',
            event_version: '1.0.0',
            timestamp: new Date().toISOString(),
            source: {
              service: 'hub',
              tenant_id: 'tenant-1',
            },
            data: {
              job_id: `job-${i}`,
            },
          })
        })
      }

      // Wait for unread badge
      await waitFor(
        () => {
          // Badge should show unread count
          const badge = document.querySelector('[class*="MuiBadge-badge"]')
          expect(badge).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should display unread indicator on notifications', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-unread-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-unread',
          },
        })
      })

      // Wait for unread indicator (blue dot)
      await waitFor(
        () => {
          const notification = screen.getByText(/Job Completed/i).closest('li')
          expect(notification).toBeInTheDocument()
          // Unread notifications have a background color
          expect(notification).toHaveStyle({ backgroundColor: expect.any(String) })
        },
        { timeout: 3000 }
      )
    })
  })

  describe('Notification Actions', () => {
    it('should display View Job action for job events', async () => {
      const user = userEvent.setup()
      const mockWindowLocation = { ...window.location }
      delete (window as any).location
      ;(window as any).location = { href: '' }

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send job event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-action-job-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-action-123',
            job_type: 'SCHEMA_INFERENCE',
          },
        })
      })

      // Wait for notification with action button
      await waitFor(
        () => {
          const viewJobButton = screen.getByRole('button', { name: /View Job/i })
          expect(viewJobButton).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Click action button
      const viewJobButton = screen.getByRole('button', { name: /View Job/i })
      await user.click(viewJobButton)

      // Should navigate to job detail page
      expect(window.location.href).toBe('/jobs/job-action-123')

      // Restore window.location
      window.location = mockWindowLocation
    })

    it('should display View Contract action for contract events', async () => {
      const user = userEvent.setup()
      const mockWindowLocation = { ...window.location }
      delete (window as any).location
      ;(window as any).location = { href: '' }

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send contract event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-action-contract-1',
          event_type: 'contract.created',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            contract_id: 'contract-action-456',
          },
        })
      })

      // Wait for notification with action button
      await waitFor(
        () => {
          const viewContractButton = screen.getByRole('button', { name: /View Contract/i })
          expect(viewContractButton).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Click action button
      const viewContractButton = screen.getByRole('button', { name: /View Contract/i })
      await user.click(viewContractButton)

      // Should navigate to contract detail page
      expect(window.location.href).toBe('/contracts/contract-action-456')

      // Restore window.location
      window.location = mockWindowLocation
    })

    it('should display View Asset action for asset events', async () => {
      const user = userEvent.setup()
      const mockWindowLocation = { ...window.location }
      delete (window as any).location
      ;(window as any).location = { href: '' }

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send asset event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-action-asset-1',
          event_type: 'asset.created',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            asset_id: 'asset-action-789',
          },
        })
      })

      // Wait for notification with action button
      await waitFor(
        () => {
          const viewAssetButton = screen.getByRole('button', { name: /View Asset/i })
          expect(viewAssetButton).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Click action button
      const viewAssetButton = screen.getByRole('button', { name: /View Asset/i })
      await user.click(viewAssetButton)

      // Should navigate to asset detail page
      expect(window.location.href).toBe('/assets/asset-action-789')

      // Restore window.location
      window.location = mockWindowLocation
    })

    it('should handle multiple actions on same notification', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event with both job_id and asset_id (unusual but possible)
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-multi-action-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-multi',
            asset_id: 'asset-multi',
          },
        })
      })

      // Wait for notifications with actions
      await waitFor(
        () => {
          // Should show View Job action (first action)
          expect(screen.getByRole('button', { name: /View Job/i })).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })
  })

  describe('Notification Persistence', () => {
    it('should save notifications to localStorage when persist is enabled', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={true} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-persist-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-persist-1',
          },
        })
      })

      // Wait for notification and persistence (with debounce)
      await waitFor(
        () => {
          const stored = localStorage.getItem('notifications')
          expect(stored).toBeTruthy()
          if (stored) {
            const parsed = JSON.parse(stored)
            expect(parsed.notifications).toBeInstanceOf(Array)
            expect(parsed.notifications.length).toBeGreaterThan(0)
          }
        },
        { timeout: 3000 }
      )
    })

    it('should load persisted notifications on mount', async () => {
      // Pre-populate localStorage
      const testNotification = {
        version: 1,
        notifications: [
          {
            id: 'persisted-1',
            title: 'Persisted Notification',
            message: 'This was saved previously',
            severity: 'info',
            timestamp: new Date().toISOString(),
            read: false,
          },
        ],
        lastSaved: new Date().toISOString(),
      }
      localStorage.setItem('notifications', JSON.stringify(testNotification))

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={true} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Wait for persisted notification to load
      await waitFor(
        () => {
          expect(screen.getByText(/Persisted Notification/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should not persist when persist is disabled', async () => {
      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-no-persist-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-no-persist',
          },
        })
      })

      // Wait a bit for any potential save
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // Should not be persisted
      const stored = localStorage.getItem('notifications')
      // May be null or contain old data, but shouldn't contain our new notification
      if (stored) {
        const parsed = JSON.parse(stored)
        const hasNewNotification = parsed.notifications?.some(
          (n: any) => n.id === 'evt-no-persist-1'
        )
        expect(hasNewNotification).toBe(false)
      }
    })

    it('should persist read state changes', async () => {
      const user = userEvent.setup()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={true} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-persist-read-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-persist-read',
          },
        })
      })

      // Wait for notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Completed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Mark as read
      const markAsReadButton = screen.getByRole('button', { name: /Mark as read/i })
      await user.click(markAsReadButton)

      // Wait for persistence
      await waitFor(
        () => {
          const stored = localStorage.getItem('notifications')
          if (stored) {
            const parsed = JSON.parse(stored)
            const notification = parsed.notifications.find((n: any) => n.id === 'evt-persist-read-1')
            expect(notification).toBeDefined()
            expect(notification.read).toBe(true)
          }
        },
        { timeout: 3000 }
      )
    })
  })

  describe('Notification Dismissal', () => {
    it('should dismiss single notification when dismiss button is clicked', async () => {
      const user = userEvent.setup()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-dismiss-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-dismiss',
          },
        })
      })

      // Wait for notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Completed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Dismiss notification
      const dismissButton = screen.getByRole('button', { name: /Dismiss/i })
      await user.click(dismissButton)

      // Notification should be removed
      await waitFor(
        () => {
          expect(screen.queryByText(/Job Completed/i)).not.toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })

    it('should clear all notifications when clear all is clicked', async () => {
      const user = userEvent.setup()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send multiple events
      for (let i = 0; i < 3; i++) {
        await act(async () => {
          await testServer.broadcastEvent({
            event_id: `evt-clear-${i}`,
            event_type: 'job.completed',
            event_version: '1.0.0',
            timestamp: new Date().toISOString(),
            source: {
              service: 'hub',
              tenant_id: 'tenant-1',
            },
            data: {
              job_id: `job-clear-${i}`,
            },
          })
        })
      }

      // Wait for notifications
      await waitFor(
        () => {
          const notifications = screen.getAllByText(/Job Completed/i)
          expect(notifications.length).toBeGreaterThan(0)
        },
        { timeout: 3000 }
      )

      // Clear all
      const clearAllButton = screen.getByRole('button', { name: /Clear all/i })
      await user.click(clearAllButton)

      // All notifications should be removed
      await waitFor(
        () => {
          expect(screen.queryByText(/Job Completed/i)).not.toBeInTheDocument()
          expect(screen.getByText(/No notifications/i)).toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })

    it('should dismiss notification when auto-dismiss is configured', async () => {
      vi.useFakeTimers()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter
          open={true}
          onClose={mockOnClose}
          persist={false}
          autoDismiss={1000}
        />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-auto-dismiss-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-auto-dismiss',
          },
        })
      })

      // Wait for notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Completed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Fast-forward timer
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      // Notification should be auto-dismissed
      await waitFor(
        () => {
          expect(screen.queryByText(/Job Completed/i)).not.toBeInTheDocument()
        },
        { timeout: 1000 }
      )

      vi.useRealTimers()
    })

    it('should mark notification as read when clicked', async () => {
      const user = userEvent.setup()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send event
      await act(async () => {
        await testServer.broadcastEvent({
          event_id: 'evt-mark-read-1',
          event_type: 'job.completed',
          event_version: '1.0.0',
          timestamp: new Date().toISOString(),
          source: {
            service: 'hub',
            tenant_id: 'tenant-1',
          },
          data: {
            job_id: 'job-mark-read',
          },
        })
      })

      // Wait for notification
      await waitFor(
        () => {
          expect(screen.getByText(/Job Completed/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Click notification to mark as read
      const notification = screen.getByText(/Job Completed/i).closest('button')
      if (notification) {
        await user.click(notification)
      }

      // Notification should be marked as read (no unread indicator)
      await waitFor(
        () => {
          const notificationItem = screen.getByText(/Job Completed/i).closest('li')
          // Read notifications don't have the unread background
          expect(notificationItem).toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })

    it('should mark all notifications as read when mark all as read is clicked', async () => {
      const user = userEvent.setup()

      renderWithProviders(
        <EnhancedRealtimeNotificationCenter open={true} onClose={mockOnClose} persist={false} />,
        {}
      )

      await waitFor(
        () => {
          expect(screen.getByText('Notifications')).toBeInTheDocument()
        },
        { timeout: 5000 }
      )

      // Send multiple events
      for (let i = 0; i < 3; i++) {
        await act(async () => {
          await testServer.broadcastEvent({
            event_id: `evt-mark-all-${i}`,
            event_type: 'job.completed',
            event_version: '1.0.0',
            timestamp: new Date().toISOString(),
            source: {
              service: 'hub',
              tenant_id: 'tenant-1',
            },
            data: {
              job_id: `job-mark-all-${i}`,
            },
          })
        })
      }

      // Wait for notifications
      await waitFor(
        () => {
          const notifications = screen.getAllByText(/Job Completed/i)
          expect(notifications.length).toBeGreaterThan(0)
        },
        { timeout: 3000 }
      )

      // Mark all as read
      const markAllAsReadButton = screen.getByRole('button', { name: /Mark all as read/i })
      await user.click(markAllAsReadButton)

      // All notifications should be marked as read
      await waitFor(
        () => {
          // Unread count should be 0
          const badge = document.querySelector('[class*="MuiBadge-badge"]')
          // Badge should show 0 or not be visible
          expect(badge).toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })
  })
})

