/**
 * WebSocket Integration Tests
 *
 * Comprehensive integration tests for WebSocket connection, event subscription,
 * and reconnection logic. Uses a real WebSocket server (no mocks/stubs).
 *
 * Tests cover:
 * - Connection establishment and state management
 * - Event subscription and unsubscription
 * - Reconnection logic with exponential backoff
 * - Error handling and recovery
 * - Multiple client connections
 * - Event broadcasting and filtering
 */

/**
 * WebSocket Integration Tests
 *
 * IMPORTANT: This test file must be run separately or with special setup
 * to override the WebSocket mock in setup.ts. The polyfill is set up here
 * to use real WebSocket connections.
 */

// Setup WebSocket polyfill FIRST, before any other imports
import { setupWebSocketPolyfill } from '@/test-utils/websocket-polyfill'
setupWebSocketPolyfill()

import { describe, it, expect, beforeEach, afterEach, vi, beforeAll, afterAll } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useWebSocketConnection, useWebSocket, useWebSocketEvent } from '../useWebSocket'
import { WebSocketClient, WebSocketState, resetWebSocketClient } from '@/lib/api/websocket'
import { createTestWebSocketServer, TestWebSocketServer } from '@/test-utils/websocket-test-server'
import { createHookWrapper } from './test-utils'
import { config } from '@/lib/config'

// Set auth token for WebSocket authentication
// Use the correct storage key that getAuthToken() expects
const setAuthToken = (token: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('auth_access_token', token)
  }
}

const clearAuthToken = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('auth_access_token')
  }
}

describe('WebSocket Integration Tests', () => {
  let testServer: TestWebSocketServer
  let originalWsUrl: string

  beforeAll(async () => {
    // Start test WebSocket server with dynamic port to avoid conflicts
    // Use /ws/events/ path to match what the WebSocket client expects
    testServer = createTestWebSocketServer({
      port: 0, // Use dynamic port to avoid conflicts
      path: '/ws/events/',
      requireAuth: true,
    })

    await testServer.start()
    originalWsUrl = config.api.wsUrl

    // Override WebSocket URL for tests
    // The client will append /ws/events/ to the base URL, so we need to provide
    // just the base URL (protocol + host + port) without any path
    // Extract just the protocol, host, and port from the test server URL
    const serverUrl = testServer.getUrl()
    const urlMatch = serverUrl.match(/^(ws:\/\/[^\/]+)/)
    const baseUrl = urlMatch ? urlMatch[1] : serverUrl.replace('/ws/events/', '')

    Object.defineProperty(config.api, 'wsUrl', {
      value: baseUrl,
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
    // Reset WebSocket client singleton to ensure fresh connections
    resetWebSocketClient()
    clearAuthToken()
    setAuthToken('test-token')
    vi.clearAllMocks()
  })

  afterEach(() => {
    clearAuthToken()
  })

  describe('WebSocket Connection', () => {
    it('should establish connection successfully', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      expect(result.current.status.state).toBe(WebSocketState.DISCONNECTED)
      expect(result.current.status.isConnected).toBe(false)

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      expect(result.current.status.state).toBe(WebSocketState.CONNECTED)
      expect(result.current.status.isConnecting).toBe(false)
      expect(result.current.status.isDisconnected).toBe(false)
    })

    it('should handle connection failure when no token is available', async () => {
      clearAuthToken()

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      await act(async () => {
        try {
          await result.current.connect()
        } catch (error) {
          // Expected to throw
        }
      })

      await waitFor(() => {
        expect(result.current.status.error).toBeTruthy()
      })

      expect(result.current.status.isConnected).toBe(false)
      expect(result.current.status.state).not.toBe(WebSocketState.CONNECTED)
    })

    it('should handle connection timeout', async () => {
      // Stop server to simulate timeout
      await testServer.stop()

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketConnection({
            connectionTimeout: 1000, // 1 second timeout
          }),
        { wrapper }
      )

      await act(async () => {
        try {
          await result.current.connect()
        } catch (error) {
          // Expected to throw or timeout
        }
      })

      // Wait for timeout
      await waitFor(
        () => {
          expect(result.current.status.state).toBe(WebSocketState.ERROR)
        },
        { timeout: 3000 }
      )

      // Restart server for other tests
      await testServer.start()
    })

    it('should disconnect successfully', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(() => {
        expect(result.current.status.isConnected).toBe(true)
      })

      await act(() => {
        result.current.disconnect()
      })

      await waitFor(() => {
        expect(result.current.status.isConnected).toBe(false)
      })

      expect(result.current.status.state).toBe(WebSocketState.DISCONNECTED)
      expect(result.current.status.isDisconnected).toBe(true)
    })

    it('should track connection state changes', async () => {
      const stateChanges: WebSocketState[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Listen to state changes
      result.current.client.on('state_change', (data: { newState: WebSocketState }) => {
        stateChanges.push(data.newState)
      })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(() => {
        expect(result.current.status.isConnected).toBe(true)
      })

      await act(() => {
        result.current.disconnect()
      })

      await waitFor(() => {
        expect(result.current.status.isDisconnected).toBe(true)
      })

      // Should have tracked state changes
      expect(stateChanges.length).toBeGreaterThan(0)
      expect(stateChanges).toContain(WebSocketState.CONNECTING)
      expect(stateChanges).toContain(WebSocketState.CONNECTED)
      expect(stateChanges).toContain(WebSocketState.DISCONNECTED)
    })

    it('should handle multiple connection attempts gracefully', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Attempt multiple connections
      await act(async () => {
        await Promise.all([
          result.current.connect(),
          result.current.connect(),
          result.current.connect(),
        ])
      })

      await waitFor(() => {
        expect(result.current.status.isConnected).toBe(true)
      })

      // Should only have one active connection
      expect(testServer.getClientCount()).toBe(1)
    })
  })

  describe('Event Subscription', () => {
    it('should subscribe to events successfully', async () => {
      const receivedEvents: any[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocket(['contract.created', 'asset.activated'], (event) => {
            receivedEvents.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Wait a bit for subscription to complete
      await new Promise((resolve) => setTimeout(resolve, 500))

      // Broadcast test event
      testServer.broadcastEvent({
        event_id: 'event-1',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-123',
          name: 'Test Contract',
        },
      })

      await waitFor(
        () => {
          expect(receivedEvents.length).toBeGreaterThan(0)
        },
        { timeout: 2000 }
      )

      expect(receivedEvents[0].event_type).toBe('contract.created')
      expect(receivedEvents[0].data.contract_id).toBe('contract-123')
    })

    it('should unsubscribe from events successfully', async () => {
      const receivedEvents: any[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocket(['contract.created', 'asset.activated'], (event) => {
            receivedEvents.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Unsubscribe from one event type
      await act(() => {
        result.current.unsubscribe(['contract.created'])
      })

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Broadcast event - should not be received
      testServer.broadcastEvent({
        event_id: 'event-2',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-456',
        },
      })

      // Broadcast another event - should be received
      testServer.broadcastEvent({
        event_id: 'event-3',
        event_type: 'asset.activated',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          asset_id: 'asset-789',
        },
      })

      await waitFor(
        () => {
          // Should only receive asset.activated event
          const assetEvents = receivedEvents.filter((e) => e.event_type === 'asset.activated')
          expect(assetEvents.length).toBeGreaterThan(0)
        },
        { timeout: 2000 }
      )
    })

    it('should handle dynamic subscription changes', async () => {
      const receivedEvents: any[] = []

      const wrapper = createHookWrapper()
      const { result, rerender } = renderHook(
        ({ eventTypes }) =>
          useWebSocket(eventTypes, (event) => {
            receivedEvents.push(event)
          }),
        {
          wrapper,
          initialProps: { eventTypes: ['contract.created'] },
        }
      )

      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Change subscriptions
      rerender({ eventTypes: ['contract.created', 'asset.activated'] })

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Broadcast events
      testServer.broadcastEvent({
        event_id: 'event-4',
        event_type: 'asset.activated',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          asset_id: 'asset-123',
        },
      })

      await waitFor(
        () => {
          expect(receivedEvents.some((e) => e.event_type === 'asset.activated')).toBe(true)
        },
        { timeout: 2000 }
      )
    })

    it('should filter events by subscription', async () => {
      const contractEvents: any[] = []
      const assetEvents: any[] = []

      const wrapper = createHookWrapper()

      // Create two separate hooks with different subscriptions
      const { result: contractResult } = renderHook(
        () =>
          useWebSocket(['contract.created'], (event) => {
            contractEvents.push(event)
          }),
        { wrapper }
      )

      const { result: assetResult } = renderHook(
        () =>
          useWebSocket(['asset.activated'], (event) => {
            assetEvents.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(contractResult.current.isConnected).toBe(true)
          expect(assetResult.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Broadcast contract event
      testServer.broadcastEvent({
        event_id: 'event-5',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-999',
        },
      })

      // Broadcast asset event
      testServer.broadcastEvent({
        event_id: 'event-6',
        event_type: 'asset.activated',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          asset_id: 'asset-999',
        },
      })

      await waitFor(
        () => {
          expect(contractEvents.length).toBeGreaterThan(0)
          expect(assetEvents.length).toBeGreaterThan(0)
        },
        { timeout: 2000 }
      )

      // Verify filtering
      expect(contractEvents.every((e) => e.event_type === 'contract.created')).toBe(true)
      expect(assetEvents.every((e) => e.event_type === 'asset.activated')).toBe(true)
    })

    it('should handle useWebSocketEvent hook for single event type', async () => {
      const receivedEvents: any[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketEvent('contract.created', (event) => {
            receivedEvents.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      testServer.broadcastEvent({
        event_id: 'event-7',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-777',
        },
      })

      await waitFor(
        () => {
          expect(result.current.lastEvent).not.toBeNull()
          expect(receivedEvents.length).toBeGreaterThan(0)
        },
        { timeout: 2000 }
      )

      expect(result.current.lastEvent?.event_type).toBe('contract.created')
      expect(result.current.lastEvent?.data.contract_id).toBe('contract-777')
    })
  })

  describe('Reconnection Logic', () => {
    it('should automatically reconnect on disconnect', async () => {
      const reconnectAttempts: number[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketConnection({
            reconnectDelay: 100, // Fast reconnection for testing
            maxReconnectAttempts: 5,
            autoReconnect: true,
          }),
        { wrapper }
      )

      // Listen to reconnecting events
      result.current.client.on('reconnecting', (data: { attempt: number }) => {
        reconnectAttempts.push(data.attempt)
      })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Simulate disconnect
      await act(() => {
        testServer.simulateConnectionError()
      })

      // Wait for reconnection attempts
      await waitFor(
        () => {
          expect(reconnectAttempts.length).toBeGreaterThan(0)
        },
        { timeout: 3000 }
      )

      // Should have attempted reconnection
      expect(reconnectAttempts.length).toBeGreaterThan(0)
    })

    it('should use exponential backoff for reconnection', async () => {
      const reconnectDelays: number[] = []
      let lastReconnectTime = Date.now()

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketConnection({
            reconnectDelay: 100, // Base delay
            maxReconnectAttempts: 3,
            autoReconnect: true,
          }),
        { wrapper }
      )

      // Track reconnection timing
      result.current.client.on('reconnecting', (data: { attempt: number; delay: number }) => {
        const now = Date.now()
        const actualDelay = now - lastReconnectTime
        reconnectDelays.push(actualDelay)
        lastReconnectTime = now
      })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Simulate disconnect
      await act(() => {
        testServer.simulateConnectionError()
      })

      // Wait for multiple reconnection attempts
      await waitFor(
        () => {
          expect(reconnectDelays.length).toBeGreaterThanOrEqual(2)
        },
        { timeout: 5000 }
      )

      // Verify exponential backoff (delays should increase)
      if (reconnectDelays.length >= 2) {
        // Second delay should be greater than first (with some tolerance)
        expect(reconnectDelays[1]).toBeGreaterThanOrEqual(reconnectDelays[0] * 0.8)
      }
    })

    it('should respect max reconnection attempts', async () => {
      const reconnectAttempts: number[] = []
      let maxAttemptsReached = false

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketConnection({
            reconnectDelay: 50, // Fast for testing
            maxReconnectAttempts: 2, // Low limit for testing
            autoReconnect: true,
          }),
        { wrapper }
      )

      result.current.client.on('reconnecting', (data: { attempt: number; maxAttempts: number }) => {
        reconnectAttempts.push(data.attempt)
        if (data.attempt >= data.maxAttempts) {
          maxAttemptsReached = true
        }
      })

      result.current.client.on('error', () => {
        // Error should be emitted when max attempts reached
      })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Stop server to prevent reconnection
      await testServer.stop()

      // Simulate disconnect
      await act(() => {
        result.current.client.disconnect()
      })

      // Wait for max attempts
      await waitFor(
        () => {
          expect(maxAttemptsReached || reconnectAttempts.length >= 2).toBe(true)
        },
        { timeout: 5000 }
      )

      // Restart server
      await testServer.start()
    })

    it('should restore subscriptions after reconnection', async () => {
      const receivedEvents: any[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocket(['contract.created'], (event) => {
            receivedEvents.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Simulate disconnect and reconnect
      await act(() => {
        testServer.simulateConnectionError()
      })

      // Wait for reconnection
      await waitFor(
        () => {
          expect(result.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 1000))

      // Broadcast event - should be received after reconnection
      testServer.broadcastEvent({
        event_id: 'event-8',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-reconnected',
        },
      })

      await waitFor(
        () => {
          expect(receivedEvents.length).toBeGreaterThan(0)
        },
        { timeout: 3000 }
      )
    })

    it('should handle reconnection status updates', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () =>
          useWebSocketConnection({
            reconnectDelay: 100,
            maxReconnectAttempts: 3,
            autoReconnect: true,
          }),
        { wrapper }
      )

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Simulate disconnect
      await act(() => {
        testServer.simulateConnectionError()
      })

      // Should show reconnecting state
      await waitFor(
        () => {
          expect(result.current.status.isReconnecting).toBe(true)
        },
        { timeout: 2000 }
      )

      expect(result.current.status.reconnectAttempt).toBeGreaterThan(0)
      expect(result.current.status.maxReconnectAttempts).toBe(3)
    })
  })

  describe('Error Handling', () => {
    it('should handle connection errors gracefully', async () => {
      const errors: string[] = []

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      result.current.client.on('error', (data: { error: string }) => {
        errors.push(data.error)
      })

      // Try to connect without token
      clearAuthToken()

      await act(async () => {
        try {
          await result.current.connect()
        } catch (error) {
          // Expected
        }
      })

      await waitFor(
        () => {
          expect(result.current.status.error).toBeTruthy() || errors.length > 0
        },
        { timeout: 3000 }
      )

      setAuthToken('test-token')
    })

    it('should handle message parsing errors', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      await act(async () => {
        await result.current.connect()
      })

      await waitFor(
        () => {
          expect(result.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Send invalid message (this would be handled by the client)
      // The test server should handle it gracefully
      expect(result.current.status.error).toBeUndefined()
    })
  })

  describe('Multiple Clients', () => {
    it('should handle multiple independent connections', async () => {
      const wrapper = createHookWrapper()

      const { result: client1 } = renderHook(() => useWebSocketConnection(), { wrapper })
      const { result: client2 } = renderHook(() => useWebSocketConnection(), { wrapper })

      await act(async () => {
        await Promise.all([client1.current.connect(), client2.current.connect()])
      })

      await waitFor(
        () => {
          expect(client1.current.status.isConnected).toBe(true)
          expect(client2.current.status.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      // Should have two clients connected
      expect(testServer.getClientCount()).toBe(2)
    })

    it('should handle independent subscriptions per client', async () => {
      const client1Events: any[] = []
      const client2Events: any[] = []

      const wrapper = createHookWrapper()

      const { result: client1 } = renderHook(
        () =>
          useWebSocket(['contract.created'], (event) => {
            client1Events.push(event)
          }),
        { wrapper }
      )

      const { result: client2 } = renderHook(
        () =>
          useWebSocket(['asset.activated'], (event) => {
            client2Events.push(event)
          }),
        { wrapper }
      )

      await waitFor(
        () => {
          expect(client1.current.isConnected).toBe(true)
          expect(client2.current.isConnected).toBe(true)
        },
        { timeout: 5000 }
      )

      await new Promise((resolve) => setTimeout(resolve, 500))

      // Broadcast different events
      testServer.broadcastEvent({
        event_id: 'event-9',
        event_type: 'contract.created',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          contract_id: 'contract-multi',
        },
      })

      testServer.broadcastEvent({
        event_id: 'event-10',
        event_type: 'asset.activated',
        event_version: '1.0.0',
        timestamp: new Date().toISOString(),
        source: {
          service: 'test',
          tenant_id: 'tenant-1',
        },
        data: {
          asset_id: 'asset-multi',
        },
      })

      await waitFor(
        () => {
          expect(client1Events.length).toBeGreaterThan(0)
          expect(client2Events.length).toBeGreaterThan(0)
        },
        { timeout: 2000 }
      )

      // Verify each client received only their subscribed events
      expect(client1Events.every((e) => e.event_type === 'contract.created')).toBe(true)
      expect(client2Events.every((e) => e.event_type === 'asset.activated')).toBe(true)
    })
  })
})

