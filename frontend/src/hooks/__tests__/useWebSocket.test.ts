/**
 * WebSocket Hooks Tests
 *
 * Comprehensive tests for WebSocket hooks covering:
 * - useWebSocketConnection() - Connection status hook
 * - useWebSocket() - Event subscription hook
 * - useWebSocketEvent() - Single event type hook
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import {
  useWebSocketConnection,
  useWebSocket,
  useWebSocketEvent,
} from '../useWebSocket'
import { WebSocketClient, WebSocketState } from '@/lib/api/websocket'
import { createHookWrapper } from './test-utils'

// Mock the WebSocket client
vi.mock('@/lib/api/websocket', async () => {
  const actual = await vi.importActual('@/lib/api/websocket')
  return {
    ...actual,
    getWebSocketClient: vi.fn(),
  }
})

// Mock WebSocket API
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  url: string
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    // Simulate connection after a short delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      if (this.onopen) {
        this.onopen(new Event('open'))
      }
    }, 10)
  }

  send(data: string) {
    // Mock send
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }))
    }
  }

  // Helper to simulate receiving a message
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }
}

// Replace global WebSocket with mock
global.WebSocket = MockWebSocket as any

describe('WebSocket Hooks', () => {
  let mockClient: WebSocketClient
  let eventHandlers: Map<string, Set<Function>>

  beforeEach(async () => {
    eventHandlers = new Map()
    mockClient = {
      getState: vi.fn(() => WebSocketState.DISCONNECTED),
      isConnected: vi.fn(() => false),
      connect: vi.fn(),
      disconnect: vi.fn(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
      getSubscriptions: vi.fn(() => []),
      on: vi.fn((eventName: string, handler: Function) => {
        if (!eventHandlers.has(eventName)) {
          eventHandlers.set(eventName, new Set())
        }
        eventHandlers.get(eventName)!.add(handler)
        return () => {
          eventHandlers.get(eventName)?.delete(handler)
        }
      }),
      off: vi.fn(),
    } as any

    const websocketModule = await import('@/lib/api/websocket')
    vi.mocked(websocketModule.getWebSocketClient).mockReturnValue(mockClient)
  })

  afterEach(() => {
    vi.clearAllMocks()
    eventHandlers.clear()
  })

  describe('useWebSocketConnection', () => {
    it('should provide connection status', () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.DISCONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(false)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      expect(result.current.status.state).toBe(WebSocketState.DISCONNECTED)
      expect(result.current.status.isConnected).toBe(false)
      expect(result.current.status.isDisconnected).toBe(true)
    })

    it('should update status when connected', async () => {
      // Start disconnected
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.DISCONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(false)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Wait for hook to set up event listeners
      await waitFor(() => {
        expect(eventHandlers.has('state_change')).toBe(true)
      })

      // Simulate state change - update mock BEFORE triggering event
      // because updateStatus() will read from the client
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      // Trigger state change event
      act(() => {
        const handlers = eventHandlers.get('state_change')
        if (handlers) {
          handlers.forEach((handler) => handler({ newState: WebSocketState.CONNECTED }))
        }
      })

      await waitFor(() => {
        expect(result.current.status.isConnected).toBe(true)
        expect(result.current.status.state).toBe(WebSocketState.CONNECTED)
      })
    })

    it('should call connect method', async () => {
      vi.mocked(mockClient.connect).mockResolvedValue(undefined)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Wait for hook to initialize
      await waitFor(() => {
        expect(result.current.connect).toBeDefined()
      })

      await act(async () => {
        await result.current.connect()
      })

      expect(mockClient.connect).toHaveBeenCalled()
    })

    it('should call disconnect method', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Wait for hook to initialize
      await waitFor(() => {
        expect(result.current.disconnect).toBeDefined()
      })

      act(() => {
        result.current.disconnect()
      })

      expect(mockClient.disconnect).toHaveBeenCalled()
    })

    it('should handle reconnecting state', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Wait for hook to set up event listeners
      await waitFor(() => {
        expect(eventHandlers.has('reconnecting')).toBe(true)
      })

      act(() => {
        const handlers = eventHandlers.get('reconnecting')
        if (handlers) {
          handlers.forEach((handler) =>
            handler({ attempt: 1, maxAttempts: 5, delay: 1000 })
          )
        }
      })

      await waitFor(() => {
        expect(result.current.status.isReconnecting).toBe(true)
        expect(result.current.status.reconnectAttempt).toBe(1)
        expect(result.current.status.maxReconnectAttempts).toBe(5)
      })
    })

    it('should handle errors', async () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useWebSocketConnection(), { wrapper })

      // Wait for hook to set up event listeners
      await waitFor(() => {
        expect(eventHandlers.has('error')).toBe(true)
      })

      act(() => {
        const handlers = eventHandlers.get('error')
        if (handlers) {
          handlers.forEach((handler) => handler({ error: 'Connection failed' }))
        }
      })

      await waitFor(() => {
        expect(result.current.status.error).toBe('Connection failed')
      })
    })
  })

  describe('useWebSocket', () => {
    it('should subscribe to events when connected', async () => {
      // Start disconnected
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.DISCONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(false)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useWebSocket(['contract.created', 'asset.activated'], onEvent),
        { wrapper }
      )

      // Wait for hook to set up event listeners
      await waitFor(() => {
        expect(eventHandlers.has('state_change')).toBe(true)
      })

      // Update mock to return connected state
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      // Simulate connection
      act(() => {
        const handlers = eventHandlers.get('state_change')
        if (handlers) {
          handlers.forEach((handler) => handler({ newState: WebSocketState.CONNECTED }))
        }
      })

      await waitFor(() => {
        expect(mockClient.subscribe).toHaveBeenCalledWith(['contract.created', 'asset.activated'])
      })
    })

    it('should call onEvent when event is received', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      renderHook(() => useWebSocket(['contract.created'], onEvent), { wrapper })

      // Simulate event
      act(() => {
        const handlers = eventHandlers.get('event')
        if (handlers) {
          handlers.forEach((handler) =>
            handler({
              event_id: 'evt-1',
              event_type: 'contract.created',
              event_version: '1.0.0',
              timestamp: '2024-01-01T00:00:00Z',
              source: { service: 'hub', tenant_id: 'tenant-1' },
              data: { contract_id: 'contract-1' },
            })
          )
        }
      })

      await waitFor(() => {
        expect(onEvent).toHaveBeenCalledWith(
          expect.objectContaining({
            event_type: 'contract.created',
            data: { contract_id: 'contract-1' },
          })
        )
      })
    })

    it('should update subscriptions when eventTypes change', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { rerender } = renderHook(
        ({ eventTypes }) => useWebSocket(eventTypes, onEvent),
        {
          wrapper,
          initialProps: { eventTypes: ['contract.created'] },
        }
      )

      // Simulate connection
      act(() => {
        const handlers = eventHandlers.get('state_change')
        if (handlers) {
          handlers.forEach((handler) => handler({ newState: WebSocketState.CONNECTED }))
        }
      })

      await waitFor(() => {
        expect(mockClient.subscribe).toHaveBeenCalledWith(['contract.created'])
      })

      // Change event types
      rerender({ eventTypes: ['contract.created', 'asset.activated'] })

      await waitFor(() => {
        expect(mockClient.subscribe).toHaveBeenCalledWith(['asset.activated'])
      })
    })

    it('should unsubscribe on cleanup', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { unmount } = renderHook(
        () => useWebSocket(['contract.created'], onEvent),
        { wrapper }
      )

      // Simulate connection
      act(() => {
        const handlers = eventHandlers.get('state_change')
        if (handlers) {
          handlers.forEach((handler) => handler({ newState: WebSocketState.CONNECTED }))
        }
      })

      await waitFor(() => {
        expect(mockClient.subscribe).toHaveBeenCalled()
      })

      unmount()

      await waitFor(() => {
        expect(mockClient.unsubscribe).toHaveBeenCalledWith(['contract.created'])
      })
    })
  })

  describe('useWebSocketEvent', () => {
    it('should subscribe to single event type', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useWebSocketEvent('job.completed', onEvent),
        { wrapper }
      )

      // Simulate connection
      act(() => {
        const handlers = eventHandlers.get('state_change')
        if (handlers) {
          handlers.forEach((handler) => handler({ newState: WebSocketState.CONNECTED }))
        }
      })

      await waitFor(() => {
        expect(mockClient.subscribe).toHaveBeenCalledWith(['job.completed'])
      })
    })

    it('should store last event of correct type', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useWebSocketEvent('job.completed', onEvent),
        { wrapper }
      )

      // Simulate event
      act(() => {
        const handlers = eventHandlers.get('event')
        if (handlers) {
          handlers.forEach((handler) =>
            handler({
              event_id: 'evt-1',
              event_type: 'job.completed',
              event_version: '1.0.0',
              timestamp: '2024-01-01T00:00:00Z',
              source: { service: 'hub', tenant_id: 'tenant-1' },
              data: {
                job_id: 'job-1',
                job_type: 'DQ_RUN',
                resource_type: 'DATASET',
                resource_id: 'dataset-1',
                started_at: '2024-01-01T00:00:00Z',
                completed_at: '2024-01-01T00:05:00Z',
              },
            })
          )
        }
      })

      await waitFor(() => {
        expect(result.current.lastEvent).toBeTruthy()
        expect(result.current.lastEvent?.event_type).toBe('job.completed')
        expect(result.current.lastEvent?.data.job_id).toBe('job-1')
        expect(onEvent).toHaveBeenCalled()
      })
    })

    it('should ignore events of different types', async () => {
      vi.mocked(mockClient.getState).mockReturnValue(WebSocketState.CONNECTED)
      vi.mocked(mockClient.isConnected).mockReturnValue(true)

      const onEvent = vi.fn()
      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useWebSocketEvent('job.completed', onEvent),
        { wrapper }
      )

      // Simulate different event type
      act(() => {
        const handlers = eventHandlers.get('event')
        if (handlers) {
          handlers.forEach((handler) =>
            handler({
              event_id: 'evt-1',
              event_type: 'job.started', // Different type
              event_version: '1.0.0',
              timestamp: '2024-01-01T00:00:00Z',
              source: { service: 'hub', tenant_id: 'tenant-1' },
              data: { job_id: 'job-1' },
            })
          )
        }
      })

      await waitFor(() => {
        expect(result.current.lastEvent).toBeNull()
        expect(onEvent).not.toHaveBeenCalled()
      })
    })
  })
})

