/**
 * WebSocket Test Server
 *
 * Real WebSocket server for integration testing.
 * Provides a test server that can simulate various WebSocket scenarios
 * without mocking the WebSocket implementation.
 */

import { WebSocketServer, WebSocket as WSSocket } from 'ws'
import { EventEmitter } from 'events'

// Use browser WebSocket type for client connections in tests
type WebSocket = WSSocket

export interface TestWebSocketServerOptions {
  port?: number
  path?: string
  requireAuth?: boolean
  simulateDelay?: number
  simulateErrors?: boolean
}

export interface TestEvent {
  event_id: string
  event_type: string
  event_version: string
  timestamp: string
  source: {
    service: string
    tenant_id: string
    user_id?: string
  }
  data: Record<string, any>
}

/**
 * Test WebSocket Server
 *
 * A real WebSocket server for integration testing.
 * Supports:
 * - Connection handling
 * - Event subscription/unsubscription
 * - Event broadcasting
 * - Authentication simulation
 * - Error simulation
 */
export class TestWebSocketServer extends EventEmitter {
  private server: WebSocketServer | null = null
  private clients: Set<WebSocket> = new Set()
  private subscriptions: Map<WebSocket, Set<string>> = new Map()
  private port: number
  private path: string
  private requireAuth: boolean
  private simulateDelay: number
  private simulateErrors: boolean

  constructor(options: TestWebSocketServerOptions = {}) {
    super()
    // Use dynamic port (0) to avoid conflicts, or use provided port
    this.port = options.port ?? 0
    this.path = options.path || '/ws'
    this.requireAuth = options.requireAuth ?? false
    this.simulateDelay = options.simulateDelay || 0
    this.simulateErrors = options.simulateErrors ?? false
  }

  /**
   * Start the WebSocket server
   * Tries to start on the configured port, and if that fails, tries alternative ports
   */
  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      const tryStart = (port: number, attempts: number = 0): void => {
        try {
          // If server already exists, close it first
          if (this.server) {
            this.server.close(() => {
              this.server = null
              tryStart(port, attempts)
            })
            return
          }

          this.server = new WebSocketServer({
            port,
            path: this.path,
          })

          this.server.on('connection', (ws: WebSocket, req) => {
            this.handleConnection(ws, req)
          })

          this.server.on('error', (error: any) => {
            // If port is in use, try next port
            if (error.code === 'EADDRINUSE' && attempts < 10) {
              this.server?.close()
              this.server = null
              const nextPort = port + 1
              this.port = nextPort
              tryStart(nextPort, attempts + 1)
              return
            }
            this.emit('error', error)
            reject(error)
          })

          this.server.on('listening', () => {
            // Update port if it was auto-assigned (port 0) or changed
            const address = this.server?.address()
            if (address && typeof address === 'object') {
              this.port = address.port
            } else {
              this.port = port // Fallback to the port we tried
            }
            this.emit('listening')
            resolve()
          })
        } catch (error) {
          reject(error)
        }
      }

      tryStart(this.port)
    })
  }

  /**
   * Stop the WebSocket server
   */
  stop(): Promise<void> {
    return new Promise((resolve) => {
      // Close all client connections
      this.clients.forEach((client) => {
        client.close()
      })
      this.clients.clear()
      this.subscriptions.clear()

      // Close server
      if (this.server) {
        this.server.close(() => {
          this.server = null
          this.emit('closed')
          resolve()
        })
      } else {
        resolve()
      }
    })
  }

  /**
   * Get server URL
   */
  getUrl(): string {
    return `ws://localhost:${this.port}${this.path}`
  }

  /**
   * Broadcast an event to all subscribed clients
   */
  broadcastEvent(event: TestEvent): void {
    const message = JSON.stringify({
      type: 'event',
      data: event,
    })

    this.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        const subscriptions = this.subscriptions.get(client) || new Set()
        if (subscriptions.has(event.event_type) || subscriptions.size === 0) {
          if (this.simulateDelay > 0) {
            setTimeout(() => {
              client.send(message)
            }, this.simulateDelay)
          } else {
            client.send(message)
          }
        }
      }
    })
  }

  /**
   * Send an event to a specific client
   */
  sendEventToClient(client: WebSocket, event: TestEvent): void {
    if (client.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({
        type: 'event',
        data: event,
      })
      client.send(message)
    }
  }

  /**
   * Simulate connection error
   */
  simulateConnectionError(): void {
    this.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.close(1006, 'Simulated error')
      }
    })
  }

  /**
   * Get number of connected clients
   */
  getClientCount(): number {
    return this.clients.size
  }

  /**
   * Get subscriptions for a client
   */
  getClientSubscriptions(client: WebSocket): string[] {
    return Array.from(this.subscriptions.get(client) || [])
  }

  /**
   * Handle new connection
   */
  private handleConnection(ws: WebSocket, req: any): void {
    // Debug logging
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[TestWebSocketServer] New connection attempt')
      console.log('[TestWebSocketServer] Request URL:', req.url)
      console.log('[TestWebSocketServer] Request headers:', req.headers)
    }

    // Check authentication if required
    if (this.requireAuth) {
      const token = this.extractToken(req)
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.log('[TestWebSocketServer] Extracted token:', token ? 'present' : 'missing')
      }
      if (!token || token !== 'test-token') {
        if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
          console.error('[TestWebSocketServer] Authentication failed, closing connection')
        }
        ws.close(1008, 'Unauthorized')
        return
      }
    }

    this.clients.add(ws)
    this.subscriptions.set(ws, new Set())

    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[TestWebSocketServer] Connection established, client count:', this.clients.size)
    }

    // Send connection confirmation
    ws.send(
      JSON.stringify({
        type: 'connected',
        message: 'Connection established',
      })
    )

    // Handle messages
    ws.on('message', (data: Buffer) => {
      this.handleMessage(ws, data)
    })

    // Handle close
    ws.on('close', () => {
      this.clients.delete(ws)
      this.subscriptions.delete(ws)
      this.emit('client_disconnected', ws)
    })

    // Handle errors
    ws.on('error', (error) => {
      this.emit('client_error', error)
    })

    this.emit('client_connected', ws)
  }

  /**
   * Handle incoming message
   */
  private handleMessage(ws: WebSocket, data: Buffer): void {
    try {
      const message = JSON.parse(data.toString())

      if (this.simulateErrors && Math.random() > 0.7) {
        ws.send(
          JSON.stringify({
            type: 'error',
            error: 'Simulated error',
          })
        )
        return
      }

      switch (message.type) {
        case 'subscribe':
          this.handleSubscribe(ws, message.data?.event_types || [])
          break
        case 'unsubscribe':
          this.handleUnsubscribe(ws, message.data?.event_types || [])
          break
        case 'ping':
          ws.send(
            JSON.stringify({
              type: 'pong',
              timestamp: new Date().toISOString(),
            })
          )
          break
        default:
          ws.send(
            JSON.stringify({
              type: 'error',
              error: `Unknown message type: ${message.type}`,
            })
          )
      }
    } catch (error) {
      ws.send(
        JSON.stringify({
          type: 'error',
          error: 'Invalid message format',
        })
      )
    }
  }

  /**
   * Handle subscription
   */
  private handleSubscribe(ws: WebSocket, eventTypes: string[]): void {
    const subscriptions = this.subscriptions.get(ws) || new Set()
    eventTypes.forEach((eventType) => {
      subscriptions.add(eventType)
    })
    this.subscriptions.set(ws, subscriptions)

    ws.send(
      JSON.stringify({
        type: 'subscription_confirmed',
        data: {
          event_types: eventTypes,
        },
      })
    )
  }

  /**
   * Handle unsubscription
   */
  private handleUnsubscribe(ws: WebSocket, eventTypes: string[]): void {
    const subscriptions = this.subscriptions.get(ws) || new Set()
    eventTypes.forEach((eventType) => {
      subscriptions.delete(eventType)
    })
    this.subscriptions.set(ws, subscriptions)

    ws.send(
      JSON.stringify({
        type: 'subscription_confirmed',
        data: {
          event_types: eventTypes,
          action: 'unsubscribed',
        },
      })
    )
  }

  /**
   * Extract token from request
   */
  private extractToken(req: any): string | null {
    // Check query parameter
    const url = new URL(req.url || '', `http://localhost:${this.port}`)
    const token = url.searchParams.get('token')
    if (token) {
      return token
    }

    // Check Authorization header
    const authHeader = req.headers.authorization
    if (authHeader && authHeader.startsWith('Bearer ')) {
      return authHeader.substring(7)
    }

    return null
  }
}

/**
 * Create a test WebSocket server instance
 */
export function createTestWebSocketServer(
  options?: TestWebSocketServerOptions
): TestWebSocketServer {
  return new TestWebSocketServer(options)
}

