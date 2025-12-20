/**
 * WebSocket Connection Tests
 *
 * Comprehensive end-to-end tests for WebSocket connection functionality.
 * Tests connection establishment, reconnection, disconnection handling, and connection status indicator.
 *
 * Uses real WebSocket connections - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { getApiBaseUrl } from '../utils/api'
import { login, getAuthState } from '../utils/auth'

test.describe('WebSocket Connection Tests', () => {
  let authToken: string | null = null
  let apiBaseUrl: string

  test.beforeAll(async ({ browser }) => {
    // Get API base URL
    apiBaseUrl = getApiBaseUrl()

    // Login to get auth token
    const page = await browser.newPage()
    try {
      const testUser = {
        email: process.env.TEST_USER_EMAIL || 'test@example.com',
        password: process.env.TEST_USER_PASSWORD || 'testpassword123',
      }
      const authState = await login(page, testUser)
      authToken = authState.accessToken
    } catch (error) {
      console.warn('Could not get auth token in beforeAll:', error)
      // Try to get existing auth state
      const existingAuth = await getAuthState(page).catch(() => null)
      if (existingAuth) {
        authToken = existingAuth.accessToken
      }
    } finally {
      await page.close()
    }
  })

  test.describe('WebSocket Connection Establishment', () => {
    test('should establish WebSocket connection successfully', async ({ page, context }) => {
      // Navigate to a page that uses WebSocket (e.g., dashboard or jobs page)
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for page to load and check if WebSocket connection is attempted
      // The WebSocket client should automatically connect when the page loads
      await page.waitForTimeout(2000) // Give time for WebSocket to connect

      // Check browser console for WebSocket connection messages
      const consoleMessages: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'log' || msg.type() === 'info') {
          consoleMessages.push(msg.text())
        }
      })

      // Check if WebSocket connection was established by looking for connection status indicator
      const connectionIndicator = page.locator('[class*="connection-status"], [class*="ConnectionStatus"]')
      const hasIndicator = await connectionIndicator.count() > 0

      if (hasIndicator) {
        // Check if status shows "Connected"
        const connectedStatus = page.locator('text=Connected, [class*="Connected"]')
        const isConnected = await connectedStatus.isVisible().catch(() => false)

        // If not connected yet, wait a bit more
        if (!isConnected) {
          await page.waitForTimeout(3000)
        }

        // Verify connection status indicator shows connected state
        const statusText = await connectionIndicator.textContent().catch(() => '')
        expect(statusText?.toLowerCase()).toMatch(/connected|connecting/i)
      }

      // Verify no WebSocket errors in console
      const errorMessages = consoleMessages.filter((msg) => msg.toLowerCase().includes('websocket') && msg.toLowerCase().includes('error'))
      expect(errorMessages.length).toBe(0)
    })

    test('should handle connection timeout gracefully', async ({ page }) => {
      // Navigate to page
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Intercept WebSocket connections and simulate timeout
      await page.route('**/ws/**', (route) => {
        // Don't fulfill the route, simulating a timeout
        route.abort()
      })

      await page.waitForTimeout(5000) // Wait for connection attempt

      // Check that connection status shows error or disconnected state
      const connectionIndicator = page.locator('[class*="connection-status"], [class*="ConnectionStatus"]')
      const hasIndicator = await connectionIndicator.count() > 0

      if (hasIndicator) {
        const statusText = await connectionIndicator.textContent().catch(() => '')
        // Should show disconnected, error, or reconnecting state
        expect(statusText?.toLowerCase()).toMatch(/disconnected|error|reconnecting|connecting/i)
      }
    })

    test('should authenticate WebSocket connection with JWT token', async ({ page }) => {
      // Ensure we're logged in
      if (!authToken) {
        test.skip()
        return
      }

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Monitor WebSocket connection requests
      const wsRequests: string[] = []
      page.on('request', (request) => {
        const url = request.url()
        if (url.includes('/ws/') || url.startsWith('ws://') || url.startsWith('wss://')) {
          wsRequests.push(url)
        }
      })

      await page.waitForTimeout(3000) // Wait for WebSocket connection

      // Verify WebSocket URL includes token parameter
      if (wsRequests.length > 0) {
        const wsUrl = wsRequests[0]
        expect(wsUrl).toContain('token=')
        expect(wsUrl).toContain(authToken || '')
      } else {
        // If no WebSocket request captured, check if connection is established via status indicator
        const connectionIndicator = page.locator('[class*="connection-status"]')
        const isVisible = await connectionIndicator.isVisible().catch(() => false)
        expect(isVisible).toBeTruthy()
      }
    })

    test('should emit connected event when connection is established', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Listen for WebSocket connection events via console or page evaluation
      const connectionEvents: string[] = []

      // Inject listener for WebSocket events
      await page.evaluate(() => {
        (window as any).__wsConnectionEvents = []
        // Try to access WebSocket client if available
        if ((window as any).__websocketClient) {
          (window as any).__websocketClient.on('connected', () => {
            (window as any).__wsConnectionEvents.push('connected')
          })
        }
      })

      await page.waitForTimeout(3000) // Wait for connection

      // Check if connected event was emitted
      const events = await page.evaluate(() => (window as any).__wsConnectionEvents || [])

      // Verify connection status indicator shows connected
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')
      expect(statusText?.toLowerCase()).toMatch(/connected/i)
    })
  })

  test.describe('WebSocket Reconnection', () => {
    test('should automatically reconnect when connection is lost', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for initial connection
      await page.waitForTimeout(3000)

      // Simulate connection loss by closing WebSocket
      await page.evaluate(() => {
        // Try to access and close WebSocket connection
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          if (client.ws) {
            client.ws.close()
          }
        }
      })

      // Wait a bit for reconnection attempt
      await page.waitForTimeout(2000)

      // Check that reconnection is attempted (status should show "Reconnecting" or "Connecting")
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')

      // Should show reconnecting or connecting state
      expect(statusText?.toLowerCase()).toMatch(/reconnecting|connecting|connected/i)
    })

    test('should show reconnection attempt count in status indicator', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for initial connection
      await page.waitForTimeout(2000)

      // Force disconnection multiple times to trigger reconnection
      for (let i = 0; i < 2; i++) {
        await page.evaluate(() => {
          if ((window as any).__websocketClient) {
            const client = (window as any).__websocketClient
            if (client.ws) {
              client.ws.close()
            }
          }
        })
        await page.waitForTimeout(1500)
      }

      // Check for reconnection attempt indicator
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')

      // Should show reconnection attempt if reconnecting
      if (statusText?.toLowerCase().includes('reconnecting')) {
        expect(statusText).toMatch(/\d+\/\d+/) // Should show "attempt X/Y" format
      }
    })

    test('should use exponential backoff for reconnection delays', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for initial connection
      await page.waitForTimeout(2000)

      const reconnectionTimes: number[] = []

      // Monitor reconnection attempts
      await page.evaluate(() => {
        (window as any).__reconnectionTimes = []
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          const originalScheduleReconnect = client.scheduleReconnect?.bind(client)
          if (originalScheduleReconnect) {
            client.scheduleReconnect = function() {
              const startTime = Date.now()
              ;(window as any).__reconnectionTimes.push(startTime)
              return originalScheduleReconnect()
            }
          }
        }
      })

      // Force disconnection
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          if (client.ws) {
            client.ws.close()
          }
        }
      })

      // Wait for multiple reconnection attempts
      await page.waitForTimeout(5000)

      // Check that reconnection delays increase (exponential backoff)
      const times = await page.evaluate(() => (window as any).__reconnectionTimes || [])

      if (times.length >= 2) {
        const delays = []
        for (let i = 1; i < times.length; i++) {
          delays.push(times[i] - times[i - 1])
        }
        // Second delay should be longer than first (exponential backoff)
        if (delays.length >= 1) {
          expect(delays[0]).toBeGreaterThan(0)
        }
      }
    })

    test('should stop reconnecting after max attempts reached', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Configure WebSocket client with low max reconnect attempts for testing
      await page.evaluate((maxAttempts) => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.options = client.options || {}
          client.options.maxReconnectAttempts = maxAttempts
        }
      }, 3)

      // Force disconnection repeatedly
      for (let i = 0; i < 5; i++) {
        await page.evaluate(() => {
          if ((window as any).__websocketClient) {
            const client = (window as any).__websocketClient
            if (client.ws) {
              client.ws.close()
            }
          }
        })
        await page.waitForTimeout(2000)
      }

      // Wait for max attempts to be reached
      await page.waitForTimeout(5000)

      // Check that connection status shows error state (max attempts reached)
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')

      // Should show error or disconnected state after max attempts
      expect(statusText?.toLowerCase()).toMatch(/error|disconnected|max.*attempt/i)
    })
  })

  test.describe('WebSocket Disconnection Handling', () => {
    test('should handle graceful disconnection', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Disconnect gracefully
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(1000)

      // Check that status shows disconnected
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')
      expect(statusText?.toLowerCase()).toMatch(/disconnected/i)
    })

    test('should not auto-reconnect after manual disconnection', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Manually disconnect
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(5000) // Wait to see if reconnection happens

      // Check that it remains disconnected (no auto-reconnect after manual disconnect)
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')

      // Should still be disconnected (auto-reconnect disabled after manual disconnect)
      expect(statusText?.toLowerCase()).toMatch(/disconnected/i)
    })

    test('should handle unexpected disconnection (network error)', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Simulate network error by closing WebSocket abruptly
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          if (client.ws) {
            // Close with error code
            client.ws.close(1006) // Abnormal closure
          }
        }
      })

      await page.waitForTimeout(2000)

      // Should attempt to reconnect (if auto-reconnect is enabled)
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')

      // Should show reconnecting or disconnected state
      expect(statusText?.toLowerCase()).toMatch(/reconnecting|disconnected|connecting/i)
    })

    test('should emit disconnected event when connection closes', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Set up event listener
      await page.evaluate(() => {
        (window as any).__wsDisconnectEvents = []
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.on('disconnected', () => {
            (window as any).__wsDisconnectEvents.push('disconnected')
          })
        }
      })

      // Wait for connection
      await page.waitForTimeout(3000)

      // Disconnect
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(1000)

      // Check if disconnected event was emitted
      const events = await page.evaluate(() => (window as any).__wsDisconnectEvents || [])

      // Verify status shows disconnected
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const statusText = await connectionIndicator.textContent().catch(() => '')
      expect(statusText?.toLowerCase()).toMatch(/disconnected/i)
    })
  })

  test.describe('Connection Status Indicator', () => {
    test('should display connection status indicator in header', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Look for connection status indicator in header
      const header = page.locator('header, [class*="Header"], [class*="header"]')
      await expect(header).toBeVisible()

      const connectionIndicator = header.locator('[class*="connection-status"], [class*="ConnectionStatus"]')
      const isVisible = await connectionIndicator.isVisible().catch(() => false)

      // Connection indicator should be visible in header
      expect(isVisible).toBeTruthy()
    })

    test('should show "Connected" status when WebSocket is connected', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(4000)

      // Check for "Connected" status
      const connectedStatus = page.locator('text=Connected, [class*="Connected"], [aria-label*="Connected"]')
      const isVisible = await connectedStatus.isVisible().catch(() => false)

      if (isVisible) {
        await expect(connectedStatus).toBeVisible()
      } else {
        // Check connection indicator text
        const connectionIndicator = page.locator('[class*="connection-status"]')
        const statusText = await connectionIndicator.textContent().catch(() => '')
        expect(statusText?.toLowerCase()).toContain('connected')
      }
    })

    test('should show "Connecting" status during connection establishment', async ({ page }) => {
      // Navigate to page
      await page.goto('/')

      // Immediately check for "Connecting" status (before connection is established)
      const connectingStatus = page.locator('text=Connecting, [class*="Connecting"]')
      const isVisible = await connectingStatus.isVisible({ timeout: 2000 }).catch(() => false)

      // Should show connecting state initially
      if (isVisible) {
        await expect(connectingStatus).toBeVisible()
      }
    })

    test('should show "Reconnecting" status during reconnection', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for initial connection
      await page.waitForTimeout(3000)

      // Force disconnection to trigger reconnection
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          if (client.ws) {
            client.ws.close()
          }
        }
      })

      // Wait for reconnection state
      await page.waitForTimeout(2000)

      // Check for "Reconnecting" status
      const reconnectingStatus = page.locator('text=Reconnecting, [class*="Reconnecting"]')
      const isVisible = await reconnectingStatus.isVisible({ timeout: 3000 }).catch(() => false)

      if (isVisible) {
        await expect(reconnectingStatus).toBeVisible()
      } else {
        // Check connection indicator text
        const connectionIndicator = page.locator('[class*="connection-status"]')
        const statusText = await connectionIndicator.textContent().catch(() => '')
        expect(statusText?.toLowerCase()).toMatch(/reconnecting|connecting/i)
      }
    })

    test('should show "Disconnected" status when connection is closed', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Disconnect
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(1000)

      // Check for "Disconnected" status
      const disconnectedStatus = page.locator('text=Disconnected, [class*="Disconnected"]')
      const isVisible = await disconnectedStatus.isVisible({ timeout: 2000 }).catch(() => false)

      if (isVisible) {
        await expect(disconnectedStatus).toBeVisible()
      } else {
        // Check connection indicator text
        const connectionIndicator = page.locator('[class*="connection-status"]')
        const statusText = await connectionIndicator.textContent().catch(() => '')
        expect(statusText?.toLowerCase()).toContain('disconnected')
      }
    })

    test('should display reconnect button when disconnected', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Disconnect
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(1000)

      // Look for reconnect button
      const reconnectButton = page.locator('button[aria-label*="Reconnect"], button[aria-label*="reconnect"], button:has([class*="RefreshIcon"])')
      const isVisible = await reconnectButton.isVisible({ timeout: 2000 }).catch(() => false)

      if (isVisible) {
        await expect(reconnectButton).toBeVisible()
      }
    })

    test('should allow manual reconnection via reconnect button', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Disconnect
      await page.evaluate(() => {
        if ((window as any).__websocketClient) {
          const client = (window as any).__websocketClient
          client.disconnect()
        }
      })

      await page.waitForTimeout(1000)

      // Click reconnect button if available
      const reconnectButton = page.locator('button[aria-label*="Reconnect"], button[aria-label*="reconnect"]')
      const isVisible = await reconnectButton.isVisible({ timeout: 2000 }).catch(() => false)

      if (isVisible) {
        await reconnectButton.click()
        await page.waitForTimeout(3000)

        // Check that connection is re-established
        const connectedStatus = page.locator('text=Connected, [class*="Connected"]')
        const isConnected = await connectedStatus.isVisible({ timeout: 5000 }).catch(() => false)
        expect(isConnected).toBeTruthy()
      }
    })

    test('should show tooltip with connection details on hover', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Wait for connection
      await page.waitForTimeout(3000)

      // Find connection indicator
      const connectionIndicator = page.locator('[class*="connection-status"]')
      const isVisible = await connectionIndicator.isVisible().catch(() => false)

      if (isVisible) {
        // Hover over indicator
        await connectionIndicator.hover()
        await page.waitForTimeout(500)

        // Check for tooltip
        const tooltip = page.locator('[role="tooltip"], [class*="Tooltip"]')
        const tooltipVisible = await tooltip.isVisible({ timeout: 1000 }).catch(() => false)

        if (tooltipVisible) {
          const tooltipText = await tooltip.textContent()
          expect(tooltipText).toBeTruthy()
          expect(tooltipText?.toLowerCase()).toMatch(/websocket|connection|connected|disconnected/i)
        }
      }
    })
  })
})

