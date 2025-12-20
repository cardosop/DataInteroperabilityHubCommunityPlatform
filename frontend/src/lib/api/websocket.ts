/**
 * WebSocket Client
 *
 * Comprehensive WebSocket client for real-time event updates.
 * Features:
 * - Connection management with automatic reconnection
 * - Exponential backoff reconnection strategy
 * - Event subscription/unsubscription
 * - Ping/pong keep-alive mechanism
 * - Authentication via JWT token
 * - Type-safe event handling
 *
 * @example
 * ```ts
 * const ws = new WebSocketClient()
 *
 * ws.on('connected', () => {
 *   ws.subscribe(['contract.created', 'asset.activated'])
 * })
 *
 * ws.on('event', (event) => {
 *   console.log('Received event:', event)
 * })
 *
 * ws.connect()
 * ```
 */

import { config } from '../config'
import { getAuthToken } from './auth'

/**
 * WebSocket connection states
 */
export enum WebSocketState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
}

/**
 * WebSocket message types (client to server)
 */
export enum WebSocketMessageType {
  SUBSCRIBE = 'subscribe',
  UNSUBSCRIBE = 'unsubscribe',
  PING = 'ping',
}

/**
 * WebSocket message types (server to client)
 */
export enum WebSocketServerMessageType {
  EVENT = 'event',
  SUBSCRIPTION_CONFIRMED = 'subscription_confirmed',
  SUBSCRIPTION_ERROR = 'subscription_error',
  ERROR = 'error',
  PONG = 'pong',
}

/**
 * WebSocket message structure
 */
export interface WebSocketMessage {
  type: string
  data?: Record<string, any>
  error?: string
  request_id?: string
  timestamp?: string
}

/**
 * Event message structure
 */
export interface EventMessage {
  event_id: string
  event_type: string
  event_version: string
  timestamp: string
  source: {
    service: string
    tenant_id: string
    user_id?: string
    request_id?: string
  }
  data: Record<string, any>
  metadata?: Record<string, any>
}

/**
 * Subscription data
 */
export interface SubscriptionData {
  event_types: string[]
  filters?: Record<string, any>
}

/**
 * Event handler type
 */
export type EventHandler<T = any> = (data: T) => void

/**
 * WebSocket client options
 */
export interface WebSocketClientOptions {
  /**
   * WebSocket URL (defaults to config.api.wsUrl)
   */
  url?: string
  /**
   * Reconnection delay in milliseconds (defaults to config.websocket.reconnectDelay)
   */
  reconnectDelay?: number
  /**
   * Maximum reconnection attempts (defaults to config.websocket.maxReconnectAttempts)
   */
  maxReconnectAttempts?: number
  /**
   * Ping interval in milliseconds (default: 30000 = 30 seconds)
   */
  pingInterval?: number
  /**
   * Connection timeout in milliseconds (default: 10000 = 10 seconds)
   */
  connectionTimeout?: number
  /**
   * Whether to automatically reconnect on disconnect (default: true)
   */
  autoReconnect?: boolean
}

/**
 * WebSocket Client Class
 *
 * Manages WebSocket connection with automatic reconnection, event subscription,
 * and keep-alive ping/pong mechanism.
 */
export class WebSocketClient {
  private ws: WebSocket | null = null
  private state: WebSocketState = WebSocketState.DISCONNECTED
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private connectionTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  private subscriptions = new Set<string>()
  private eventHandlers = new Map<string, Set<EventHandler>>()
  private options: Required<WebSocketClientOptions>
  private baseUrl: string

  /**
   * Create a new WebSocket client
   *
   * @param options - Client configuration options
   */
  constructor(options: WebSocketClientOptions = {}) {
    // Read URL from options or config (don't cache - read dynamically)
    // In test environment, always read from config to get latest value
    const url = options.url || config.api.wsUrl
    this.baseUrl = url
    this.options = {
      url: url, // Use provided URL or current config value
      reconnectDelay: options.reconnectDelay ?? config.websocket.reconnectDelay,
      maxReconnectAttempts:
        options.maxReconnectAttempts ?? config.websocket.maxReconnectAttempts,
      pingInterval: options.pingInterval ?? 30000, // 30 seconds
      connectionTimeout: options.connectionTimeout ?? 10000, // 10 seconds
      autoReconnect: options.autoReconnect ?? true,
    }

    // Debug logging in test environment
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocketClient] Created with URL:', this.options.url)
    }
  }

  /**
   * Get current connection state
   */
  getState(): WebSocketState {
    return this.state
  }

  /**
   * Check if client is connected
   */
  isConnected(): boolean {
    return this.state === WebSocketState.CONNECTED && this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Connect to WebSocket server
   *
   * @returns Promise that resolves when connection is established
   */
  async connect(): Promise<void> {
    // Debug logging
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocket] connect() called, current state:', this.state)
      console.log('[WebSocket] isConnected():', this.isConnected())
    }

    if (this.isConnected()) {
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] Already connected, returning')
      }
      return
    }

    if (this.state === WebSocketState.CONNECTING || this.state === WebSocketState.RECONNECTING) {
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] Already connecting/reconnecting, returning')
      }
      return
    }

    try {
      this.setState(WebSocketState.CONNECTING)

      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] State set to CONNECTING')
      }

      // Get access token for authentication
      const token = getAuthToken()
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] Token retrieved:', token ? 'present' : 'missing')
      }

      if (!token) {
        const error = new Error('No access token available. Please login first.')
        if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
          console.error('[WebSocket] No token available, throwing error')
        }
        throw error
      }

      // Update baseUrl from config in case it changed (for tests)
      this.baseUrl = this.options.url || config.api.wsUrl

      // Build WebSocket URL with authentication
      const url = this.buildWebSocketUrl(token)

      // Debug logging in test environment
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] Connecting to:', url)
        console.log('[WebSocket] Base URL:', this.baseUrl)
        console.log('[WebSocket] Config URL:', config.api.wsUrl)
      }

      // Create WebSocket connection
      // Debug: Check if WebSocket is the polyfill
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        const WebSocketConstructor = WebSocket as any
        console.log('[WebSocket] WebSocket constructor name:', WebSocketConstructor.name)
        console.log('[WebSocket] Is polyfill?', WebSocketConstructor.name === 'WebSocketPolyfill')
      }

      this.ws = new WebSocket(url)

      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[WebSocket] WebSocket instance created, readyState:', this.ws.readyState)
      }

      // Set up connection timeout
      this.connectionTimeoutTimer = setTimeout(() => {
        if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
          this.ws.close()
          this.handleConnectionError(new Error('Connection timeout'))
        }
      }, this.options.connectionTimeout)

      // Set up event handlers
      this.ws.onopen = () => this.handleOpen()
      this.ws.onmessage = (event) => this.handleMessage(event)
      this.ws.onerror = (error) => this.handleError(error)
      this.ws.onclose = (event) => this.handleClose(event)
    } catch (error) {
      this.handleConnectionError(error as Error)
    }
  }

  /**
   * Disconnect from WebSocket server
   *
   * @param code - Close code (default: 1000 = normal closure)
   * @param reason - Close reason
   */
  disconnect(code = 1000, reason?: string): void {
    this.options.autoReconnect = false
    this.clearTimers()

    if (this.ws) {
      this.ws.close(code, reason)
      this.ws = null
    }

    this.setState(WebSocketState.DISCONNECTED)
    this.reconnectAttempts = 0
  }

  /**
   * Subscribe to event types
   *
   * @param eventTypes - Array of event type strings (e.g., ['contract.created', 'asset.activated'])
   * @param filters - Optional filters for events
   */
  subscribe(eventTypes: string[], filters?: Record<string, any>): void {
    if (!this.isConnected()) {
      throw new Error('Cannot subscribe: WebSocket is not connected')
    }

    const subscriptionData: SubscriptionData = {
      event_types: eventTypes,
      filters: filters,
    }

    const message: WebSocketMessage = {
      type: WebSocketMessageType.SUBSCRIBE,
      data: subscriptionData,
      request_id: this.generateRequestId(),
      timestamp: new Date().toISOString(),
    }

    this.send(message)

    // Track subscriptions
    eventTypes.forEach((eventType) => {
      this.subscriptions.add(eventType)
    })
  }

  /**
   * Unsubscribe from event types
   *
   * @param eventTypes - Array of event type strings to unsubscribe from
   */
  unsubscribe(eventTypes: string[]): void {
    if (!this.isConnected()) {
      throw new Error('Cannot unsubscribe: WebSocket is not connected')
    }

    const subscriptionData: SubscriptionData = {
      event_types: eventTypes,
    }

    const message: WebSocketMessage = {
      type: WebSocketMessageType.UNSUBSCRIBE,
      data: subscriptionData,
      request_id: this.generateRequestId(),
      timestamp: new Date().toISOString(),
    }

    this.send(message)

    // Remove from tracked subscriptions
    eventTypes.forEach((eventType) => {
      this.subscriptions.delete(eventType)
    })
  }

  /**
   * Get list of subscribed event types
   */
  getSubscriptions(): string[] {
    return Array.from(this.subscriptions)
  }

  /**
   * Register event handler
   *
   * @param eventName - Event name ('connected', 'disconnected', 'error', 'event', etc.)
   * @param handler - Event handler function
   * @returns Unsubscribe function
   */
  on<T = any>(eventName: string, handler: EventHandler<T>): () => void {
    if (!this.eventHandlers.has(eventName)) {
      this.eventHandlers.set(eventName, new Set())
    }
    this.eventHandlers.get(eventName)!.add(handler)

    // Return unsubscribe function
    return () => {
      const handlers = this.eventHandlers.get(eventName)
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  /**
   * Remove event handler
   *
   * @param eventName - Event name
   * @param handler - Event handler function to remove
   */
  off(eventName: string, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventName)
    if (handlers) {
      handlers.delete(handler)
    }
  }

  /**
   * Emit event to registered handlers
   */
  private emit<T = any>(eventName: string, data: T): void {
    const handlers = this.eventHandlers.get(eventName)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data)
        } catch (error) {
          console.error(`Error in event handler for ${eventName}:`, error)
        }
      })
    }
  }

  /**
   * Build WebSocket URL with authentication
   */
  private buildWebSocketUrl(token: string): string {
    // Parse the base URL
    let baseUrl: URL
    try {
      baseUrl = new URL(this.options.url)
    } catch {
      // If URL parsing fails, assume it's a path and construct from config
      const apiUrl = new URL(config.api.baseUrl)
      baseUrl = new URL(this.options.url, apiUrl.origin)
    }

    // Use ws:// or wss:// based on protocol
    const protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:'

    // Build WebSocket URL path
    // If baseUrl already has /ws/events/, use it; otherwise append
    let wsPath = baseUrl.pathname || '/'
    if (!wsPath.endsWith('/ws/events/')) {
      // Remove trailing slash if present
      wsPath = wsPath.replace(/\/$/, '')
      // If pathname was empty, wsPath is now empty, so we just use /ws/events/
      // Otherwise, append to existing path
      if (wsPath === '') {
        wsPath = '/ws/events/'
      } else {
        // Ensure we don't have double slashes
        if (!wsPath.startsWith('/')) {
          wsPath = `/${wsPath}`
        }
        wsPath = `${wsPath}/ws/events/`
      }
    }

    const wsUrl = `${protocol}//${baseUrl.host}${wsPath}`

    // Debug logging in test environment
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocket] URL construction:', {
        baseUrl: this.baseUrl,
        optionsUrl: this.options.url,
        configUrl: config.api.wsUrl,
        parsedBaseUrl: baseUrl.toString(),
        pathname: baseUrl.pathname,
        wsPath,
        finalUrl: wsUrl,
      })
    }

    // Add authentication token as query parameter
    const wsUrlWithAuth = new URL(wsUrl)
    wsUrlWithAuth.searchParams.set('token', token)

    return wsUrlWithAuth.toString()
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    // Debug logging in test environment
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocket] Connection opened successfully')
    }

    this.clearConnectionTimeout()
    this.setState(WebSocketState.CONNECTED)
    this.reconnectAttempts = 0

    // Start ping interval
    this.startPingInterval()

    // Re-subscribe to previous subscriptions
    if (this.subscriptions.size > 0) {
      const eventTypes = Array.from(this.subscriptions)
      this.subscribe(eventTypes)
    }

    this.emit('connected', {})
  }

  /**
   * Handle WebSocket message event
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)

      switch (message.type) {
        case WebSocketServerMessageType.EVENT:
          this.handleEventMessage(message)
          break
        case WebSocketServerMessageType.SUBSCRIPTION_CONFIRMED:
          this.emit('subscription_confirmed', message.data)
          break
        case WebSocketServerMessageType.SUBSCRIPTION_ERROR:
          this.emit('subscription_error', {
            error: message.error,
            data: message.data,
          })
          break
        case WebSocketServerMessageType.PONG:
          // Pong received, connection is alive
          break
        case WebSocketServerMessageType.ERROR:
          this.emit('error', {
            error: message.error,
            request_id: message.request_id,
          })
          break
        default:
          console.warn('Unknown message type:', message.type)
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error)
      this.emit('error', { error: 'Failed to parse message' })
    }
  }

  /**
   * Handle event message
   */
  private handleEventMessage(message: WebSocketMessage): void {
    if (message.data) {
      const eventMessage: EventMessage = message.data as EventMessage
      this.emit('event', eventMessage)

      // Also emit specific event type
      this.emit(`event:${eventMessage.event_type}`, eventMessage)
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(error: Event): void {
    // Enhanced error logging in test environment
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.error('[WebSocket] Connection error:', error)
      console.error('[WebSocket] Current state:', this.state)
      console.error('[WebSocket] Ready state:', this.ws?.readyState)
      console.error('[WebSocket] URL attempted:', this.ws?.url || 'unknown')
    } else {
      console.error('WebSocket error:', error)
    }
    this.emit('error', { error: 'WebSocket error occurred' })
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    // Debug logging in test environment
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocket] Connection closed:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      })
    }

    this.clearTimers()
    this.setState(WebSocketState.DISCONNECTED)

    this.emit('disconnected', {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
    })

    // Attempt reconnection if auto-reconnect is enabled
    if (this.options.autoReconnect && !event.wasClean) {
      this.scheduleReconnect()
    }
  }

  /**
   * Handle connection error
   */
  private handleConnectionError(error: Error): void {
    this.clearConnectionTimeout()
    this.setState(WebSocketState.ERROR)
    this.emit('error', { error: error.message })

    if (this.options.autoReconnect) {
      this.scheduleReconnect()
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      this.setState(WebSocketState.ERROR)
      this.emit('error', {
        error: `Max reconnection attempts (${this.options.maxReconnectAttempts}) reached`,
      })
      return
    }

    this.setState(WebSocketState.RECONNECTING)

    // Calculate exponential backoff delay
    const delay = Math.min(
      this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      30000 // Max 30 seconds
    )

    this.reconnectAttempts++

    this.emit('reconnecting', {
      attempt: this.reconnectAttempts,
      maxAttempts: this.options.maxReconnectAttempts,
      delay,
    })

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  /**
   * Start ping interval to keep connection alive
   */
  private startPingInterval(): void {
    this.stopPingInterval()

    this.pingTimer = setInterval(() => {
      if (this.isConnected()) {
        this.sendPing()
      } else {
        this.stopPingInterval()
      }
    }, this.options.pingInterval)
  }

  /**
   * Stop ping interval
   */
  private stopPingInterval(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  /**
   * Send ping message
   */
  private sendPing(): void {
    if (!this.isConnected()) {
      return
    }

    const message: WebSocketMessage = {
      type: WebSocketMessageType.PING,
      request_id: this.generateRequestId(),
      timestamp: new Date().toISOString(),
    }

    this.send(message)
  }

  /**
   * Send message to WebSocket server
   */
  private send(message: WebSocketMessage): void {
    if (!this.isConnected()) {
      throw new Error('Cannot send message: WebSocket is not connected')
    }

    try {
      this.ws!.send(JSON.stringify(message))
    } catch (error) {
      console.error('Error sending WebSocket message:', error)
      throw error
    }
  }

  /**
   * Set connection state and emit state change event
   */
  private setState(state: WebSocketState): void {
    if (this.state !== state) {
      const oldState = this.state
      this.state = state
      this.emit('state_change', { oldState, newState: state })
    }
  }

  /**
   * Clear all timers
   */
  private clearTimers(): void {
    this.clearConnectionTimeout()
    this.stopPingInterval()

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  /**
   * Clear connection timeout
   */
  private clearConnectionTimeout(): void {
    if (this.connectionTimeoutTimer) {
      clearTimeout(this.connectionTimeoutTimer)
      this.connectionTimeoutTimer = null
    }
  }

  /**
   * Generate unique request ID
   */
  private generateRequestId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Create a singleton WebSocket client instance
 *
 * @param options - Optional client configuration
 * @returns WebSocket client instance
 */
let wsClientInstance: WebSocketClient | null = null

export function getWebSocketClient(
  options?: WebSocketClientOptions
): WebSocketClient {
  // In test environment, always create new instance if options provided
  // This allows tests to use different URLs
  if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
    if (options) {
      wsClientInstance = new WebSocketClient(options)
      return wsClientInstance
    }
  }

  if (!wsClientInstance) {
    wsClientInstance = new WebSocketClient(options)
  }
  return wsClientInstance
}

/**
 * Reset the WebSocket client singleton (useful for tests)
 */
export function resetWebSocketClient(): void {
  if (wsClientInstance) {
    wsClientInstance.disconnect()
    wsClientInstance = null
  }
}

