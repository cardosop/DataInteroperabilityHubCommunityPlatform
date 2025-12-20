/**
 * WebSocket Hooks
 *
 * React hooks for WebSocket connection and event management:
 * - useWebSocketConnection() - Connection status hook
 * - useWebSocket() - Event subscription hook
 * - useWebSocketEvent() - Single event type hook
 *
 * These hooks provide:
 * - Automatic connection management
 * - Automatic reconnection with exponential backoff
 * - Event subscription management
 * - Connection status indicators
 * - Type-safe event handling
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import {
  WebSocketClient,
  WebSocketState,
  EventMessage,
  getWebSocketClient,
  type WebSocketClientOptions,
} from '@/lib/api/websocket'
import type {
  WebSocketEvent,
  WebSocketEventType,
  EventDataForType,
} from '@/lib/api/websocket-events'

/**
 * Connection status information
 */
export interface ConnectionStatus {
  state: WebSocketState
  isConnected: boolean
  isConnecting: boolean
  isReconnecting: boolean
  isDisconnected: boolean
  reconnectAttempt?: number
  maxReconnectAttempts?: number
  error?: string
}

/**
 * useWebSocketConnection Hook
 *
 * Hook for managing WebSocket connection status.
 * Provides connection state and connection management methods.
 *
 * @param options - WebSocket client options
 * @returns Connection status and management methods
 *
 * @example
 * ```tsx
 * function ConnectionIndicator() {
 *   const { status, connect, disconnect } = useWebSocketConnection()
 *
 *   return (
 *     <div>
 *       <StatusBadge status={status.state} />
 *       {status.isConnected && <span>Connected</span>}
 *       {status.isReconnecting && (
 *         <span>Reconnecting... ({status.reconnectAttempt}/{status.maxReconnectAttempts})</span>
 *       )}
 *       <button onClick={connect}>Connect</button>
 *       <button onClick={disconnect}>Disconnect</button>
 *     </div>
 *   )
 * }
 * ```
 */
export function useWebSocketConnection(
  options?: WebSocketClientOptions
): {
  status: ConnectionStatus
  connect: () => Promise<void>
  disconnect: () => void
  client: WebSocketClient
} {
  const clientRef = useRef<WebSocketClient | null>(null)
  const [status, setStatus] = useState<ConnectionStatus>({
    state: WebSocketState.DISCONNECTED,
    isConnected: false,
    isConnecting: false,
    isReconnecting: false,
    isDisconnected: true,
  })

  // Get or create WebSocket client
  const client = useMemo(() => {
    if (!clientRef.current) {
      clientRef.current = getWebSocketClient(options)
    }
    return clientRef.current
  }, [options])

  // Update status from client state
  const updateStatus = useCallback(() => {
    const state = client.getState()
    const isConnected = client.isConnected()

    setStatus({
      state,
      isConnected,
      isConnecting: state === WebSocketState.CONNECTING,
      isReconnecting: state === WebSocketState.RECONNECTING,
      isDisconnected: state === WebSocketState.DISCONNECTED,
      error: state === WebSocketState.ERROR ? 'Connection error' : undefined,
    })
  }, [client])

  // Set up event listeners
  useEffect(() => {
    // Initial status
    updateStatus()

    // Listen to state changes
    const unsubscribeStateChange = client.on('state_change', (data: { newState: WebSocketState }) => {
      updateStatus()
    })

    // Listen to reconnecting events
    const unsubscribeReconnecting = client.on(
      'reconnecting',
      (data: { attempt: number; maxAttempts: number; delay: number }) => {
        setStatus((prev) => ({
          ...prev,
          reconnectAttempt: data.attempt,
          maxReconnectAttempts: data.maxAttempts,
        }))
      }
    )

    // Listen to errors
    const unsubscribeError = client.on('error', (data: { error: string }) => {
      setStatus((prev) => ({
        ...prev,
        error: data.error,
      }))
    })

    // Listen to connection events
    const unsubscribeConnected = client.on('connected', () => {
      updateStatus()
    })

    const unsubscribeDisconnected = client.on('disconnected', () => {
      updateStatus()
    })

    return () => {
      unsubscribeStateChange()
      unsubscribeReconnecting()
      unsubscribeError()
      unsubscribeConnected()
      unsubscribeDisconnected()
    }
  }, [client, updateStatus])

  const connect = useCallback(async () => {
    try {
      await client.connect()
      updateStatus()
    } catch (error) {
      setStatus((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Connection failed',
      }))
    }
  }, [client, updateStatus])

  const disconnect = useCallback(() => {
    client.disconnect()
    updateStatus()
  }, [client, updateStatus])

  return {
    status,
    connect,
    disconnect,
    client,
  }
}

/**
 * useWebSocket Hook
 *
 * Hook for subscribing to multiple WebSocket events.
 * Automatically manages connection and subscriptions.
 *
 * @param eventTypes - Array of event types to subscribe to
 * @param onEvent - Callback function for received events
 * @param options - WebSocket client options
 * @returns Connection status and subscription management
 *
 * @example
 * ```tsx
 * function EventListener() {
 *   const { status, isConnected } = useWebSocket(
 *     ['contract.created', 'asset.activated'],
 *     (event) => {
 *       console.log('Received event:', event)
 *       if (event.event_type === 'contract.created') {
 *         showNotification('New contract created!')
 *       }
 *     }
 *   )
 *
 *   if (!isConnected) {
 *     return <div>Connecting...</div>
 *   }
 *
 *   return <div>Listening for events...</div>
 * }
 * ```
 */
export function useWebSocket(
  eventTypes: WebSocketEventType[],
  onEvent: (event: WebSocketEvent) => void,
  options?: WebSocketClientOptions
): {
  status: ConnectionStatus
  isConnected: boolean
  subscribe: (newEventTypes: WebSocketEventType[]) => void
  unsubscribe: (eventTypesToRemove: WebSocketEventType[]) => void
  client: WebSocketClient
} {
  const { status, connect, disconnect, client } = useWebSocketConnection(options)
  const eventTypesRef = useRef<Set<WebSocketEventType>>(new Set(eventTypes))
  const onEventRef = useRef(onEvent)

  // Update callback ref when it changes
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  // Set up event listener
  useEffect(() => {
    const unsubscribe = client.on('event', (event: EventMessage) => {
      onEventRef.current(event as WebSocketEvent)
    })

    return unsubscribe
  }, [client])

  // Auto-connect when hook is mounted
  useEffect(() => {
    if (!status.isConnected && !status.isConnecting && !status.isReconnecting) {
      connect()
    }
  }, [status.isConnected, status.isConnecting, status.isReconnecting, connect])

  // Subscribe to events when connected
  useEffect(() => {
    if (status.isConnected && eventTypesRef.current.size > 0) {
      // Use a small delay to ensure connection is fully ready
      const timeoutId = setTimeout(() => {
        try {
          if (client.isConnected()) {
            client.subscribe(Array.from(eventTypesRef.current))
          }
        } catch (error) {
          console.error('Failed to subscribe to events:', error)
        }
      }, 100)

      return () => clearTimeout(timeoutId)
    }
  }, [status.isConnected, client])

  // Update subscriptions when eventTypes change
  useEffect(() => {
    const newEventTypes = new Set(eventTypes)
    const currentEventTypes = eventTypesRef.current

    // Find added and removed event types
    const added = Array.from(newEventTypes).filter((et) => !currentEventTypes.has(et))
    const removed = Array.from(currentEventTypes).filter((et) => !newEventTypes.has(et))

    // Update ref
    eventTypesRef.current = newEventTypes

    // Update subscriptions if connected
    if (status.isConnected) {
      if (added.length > 0) {
        try {
          client.subscribe(added)
        } catch (error) {
          console.error('Failed to subscribe to new events:', error)
        }
      }
      if (removed.length > 0) {
        try {
          client.unsubscribe(removed)
        } catch (error) {
          console.error('Failed to unsubscribe from events:', error)
        }
      }
    }
  }, [eventTypes, status.isConnected, client])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (status.isConnected) {
        const currentSubscriptions = Array.from(eventTypesRef.current)
        if (currentSubscriptions.length > 0) {
          try {
            client.unsubscribe(currentSubscriptions)
          } catch (error) {
            console.error('Failed to unsubscribe on cleanup:', error)
          }
        }
      }
    }
  }, [status.isConnected, client])

  const subscribe = useCallback(
    (newEventTypes: WebSocketEventType[]) => {
      const added = newEventTypes.filter((et) => !eventTypesRef.current.has(et))
      if (added.length > 0) {
        eventTypesRef.current = new Set([...eventTypesRef.current, ...added])
        if (status.isConnected) {
          try {
            client.subscribe(added)
          } catch (error) {
            console.error('Failed to subscribe:', error)
          }
        }
      }
    },
    [status.isConnected, client]
  )

  const unsubscribe = useCallback(
    (eventTypesToRemove: WebSocketEventType[]) => {
      eventTypesToRemove.forEach((et) => eventTypesRef.current.delete(et))
      if (status.isConnected) {
        try {
          client.unsubscribe(eventTypesToRemove)
        } catch (error) {
          console.error('Failed to unsubscribe:', error)
        }
      }
    },
    [status.isConnected, client]
  )

  return {
    status,
    isConnected: status.isConnected,
    subscribe,
    unsubscribe,
    client,
  }
}

/**
 * useWebSocketEvent Hook
 *
 * Hook for subscribing to a single event type.
 * Provides type-safe event handling for specific event types.
 *
 * @param eventType - Single event type to subscribe to
 * @param onEvent - Callback function for received events
 * @param options - WebSocket client options
 * @returns Connection status and event data
 *
 * @example
 * ```tsx
 * function JobStatusListener({ jobId }: { jobId: string }) {
 *   const { status, lastEvent } = useWebSocketEvent(
 *     'job.completed',
 *     (event) => {
 *       if (event.data.job_id === jobId) {
 *         showSuccess('Job completed!')
 *       }
 *     }
 *   )
 *
 *   if (lastEvent && lastEvent.data.job_id === jobId) {
 *     return <div>Job {jobId} completed!</div>
 *   }
 *
 *   return <div>Waiting for job completion...</div>
 * }
 * ```
 */
export function useWebSocketEvent<T extends WebSocketEventType>(
  eventType: T,
  onEvent?: (event: Extract<WebSocketEvent, { event_type: T }>) => void,
  options?: WebSocketClientOptions
): {
  status: ConnectionStatus
  isConnected: boolean
  lastEvent: Extract<WebSocketEvent, { event_type: T }> | null
  client: WebSocketClient
} {
  const [lastEvent, setLastEvent] =
    useState<Extract<WebSocketEvent, { event_type: T }> | null>(null)

  const handleEvent = useCallback(
    (event: WebSocketEvent) => {
      if (event.event_type === eventType) {
        const typedEvent = event as Extract<WebSocketEvent, { event_type: T }>
        setLastEvent(typedEvent)
        if (onEvent) {
          onEvent(typedEvent)
        }
      }
    },
    [eventType, onEvent]
  )

  const { status, isConnected, client } = useWebSocket([eventType], handleEvent, options)

  return {
    status,
    isConnected,
    lastEvent,
    client,
  }
}

