/**
 * WebSocket Polyfill for Test Environment
 *
 * Provides a real WebSocket implementation that connects to the test server.
 * This allows integration tests to use real WebSocket connections without mocks.
 *
 * Note: For integration tests, we use the 'ws' library directly since we're in Node.js.
 * The WebSocket mock in setup.ts is replaced with this real implementation.
 */

import { WebSocket as WS } from 'ws'

/**
 * WebSocket polyfill for browser-like API
 * Connects to Node.js ws server from browser-like environment
 */
export class WebSocketPolyfill {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  // Add name property to identify this as the polyfill
  static readonly name = 'WebSocketPolyfill'

  readyState: number = WebSocketPolyfill.CONNECTING
  url: string
  protocol: string = ''
  extensions: string = ''
  binaryType: 'blob' | 'arraybuffer' = 'blob'

  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  private ws: WS | null = null
  private listeners: Map<string, Set<Function>> = new Map()

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = typeof url === 'string' ? url : url.toString()

    // Debug logging
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocketPolyfill] Creating connection to:', this.url)
    }

    // Extract token from URL if present
    const urlObj = new URL(this.url)
    const token = urlObj.searchParams.get('token') || urlObj.searchParams.get('access_token')

    try {
      // The 'ws' library WebSocket client accepts options with headers
      // But we'll use URL query params for auth (which the test server supports)
      // and also pass headers for compatibility
      const options: any = {}

      if (token) {
        // Add Authorization header (test server checks both query param and header)
        options.headers = {
          Authorization: `Bearer ${token}`,
        }
      }

      this.ws = new WS(this.url, options)

      this.ws.on('open', () => {
        if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
          console.log('[WebSocketPolyfill] Connection opened')
        }
        this.readyState = WebSocketPolyfill.OPEN
        if (this.onopen) {
          this.onopen(new Event('open'))
        }
        this.emit('open', new Event('open'))
      })

      this.ws.on('message', (data: Buffer) => {
        const messageEvent = {
          data: data.toString(),
          type: 'message',
        } as MessageEvent

        if (this.onmessage) {
          this.onmessage(messageEvent)
        }
        this.emit('message', messageEvent)
      })

      this.ws.on('error', (error) => {
        if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
          console.error('[WebSocketPolyfill] Connection error:', error)
          console.error('[WebSocketPolyfill] URL:', this.url)
          console.error('[WebSocketPolyfill] Ready state:', this.readyState)
        }
        if (this.onerror) {
          this.onerror(new Event('error'))
        }
        this.emit('error', new Event('error'))
      })

      this.ws.on('close', (code, reason) => {
        if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
          console.log('[WebSocketPolyfill] Connection closed:', { code, reason: reason.toString() })
        }
        this.readyState = WebSocketPolyfill.CLOSED
        const closeEvent = {
          code,
          reason: reason.toString(),
          type: 'close',
          wasClean: code === 1000,
        } as CloseEvent

        if (this.onclose) {
          this.onclose(closeEvent)
        }
        this.emit('close', closeEvent)
      })
    } catch (error) {
      if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
        console.error('[WebSocketPolyfill] Constructor error:', error)
      }
      this.readyState = WebSocketPolyfill.CLOSED
      if (this.onerror) {
        this.onerror(new Event('error'))
      }
    }
  }

  send(data: string | ArrayBuffer | Blob): void {
    if (this.ws && this.readyState === WebSocketPolyfill.OPEN) {
      if (typeof data === 'string') {
        this.ws.send(data)
      } else if (data instanceof ArrayBuffer) {
        this.ws.send(Buffer.from(data))
      } else if (data instanceof Blob) {
        data.arrayBuffer().then((buffer) => {
          this.ws?.send(Buffer.from(buffer))
        })
      }
    }
  }

  close(code?: number, reason?: string): void {
    if (this.ws) {
      this.readyState = WebSocketPolyfill.CLOSING
      this.ws.close(code, reason)
    }
  }

  addEventListener(
    type: string,
    listener: EventListener | EventListenerObject | null,
    options?: boolean | AddEventListenerOptions
  ): void {
    if (!listener) return

    const handler = typeof listener === 'function' ? listener : listener.handleEvent.bind(listener)

    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(handler)
  }

  removeEventListener(
    type: string,
    listener: EventListener | EventListenerObject | null,
    options?: boolean | EventListenerOptions
  ): void {
    if (!listener) return

    const handler = typeof listener === 'function' ? listener : listener.handleEvent.bind(listener)
    const handlers = this.listeners.get(type)
    if (handlers) {
      handlers.delete(handler)
    }
  }

  dispatchEvent(event: Event): boolean {
    const handlers = this.listeners.get(event.type)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(event)
        } catch (error) {
          console.error('Error in event handler:', error)
        }
      })
    }
    return true
  }

  private emit(type: string, event: Event): void {
    this.dispatchEvent(event)
  }
}

/**
 * Setup WebSocket polyfill for test environment
 * Replaces the mock WebSocket with a real implementation
 */
export function setupWebSocketPolyfill(): void {
  if (typeof global !== 'undefined') {
    // Force replace the mock WebSocket with real implementation
    // @ts-ignore
    global.WebSocket = WebSocketPolyfill
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocketPolyfill] Replaced global.WebSocket with polyfill')
    }
  }
  if (typeof window !== 'undefined') {
    // @ts-ignore
    window.WebSocket = WebSocketPolyfill
    if (process.env.NODE_ENV === 'test' || process.env.VITEST) {
      console.log('[WebSocketPolyfill] Replaced window.WebSocket with polyfill')
    }
  }
}

