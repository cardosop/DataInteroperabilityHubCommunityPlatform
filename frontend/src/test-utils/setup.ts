/**
 * Test Setup File
 *
 * Global test setup that runs before all tests.
 * This file is automatically executed by Vitest before running tests.
 *
 * Use this file to:
 * - Configure global test utilities
 * - Set up global mocks
 * - Configure test environment
 * - Import global test utilities
 */

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeAll, afterAll, vi } from 'vitest'
import { setupMSW } from './msw/server'
// Import accessibility testing utilities to extend expect
import './accessibility'

// Extend Vitest's expect with jest-dom matchers
// This provides additional matchers like toBeInTheDocument, toHaveClass, etc.

// Cleanup after each test
// This ensures that DOM is cleaned up between tests
afterEach(() => {
  cleanup()
})

// Mock window.matchMedia
// Required for components that use media queries (e.g., responsive design)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock IntersectionObserver
// Required for components that use intersection observer (e.g., lazy loading)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as any

// Mock ResizeObserver
// Required for components that use resize observer (e.g., virtual scrolling)
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any

// Mock window.scrollTo
// Prevents scroll errors in tests
window.scrollTo = vi.fn()

// Mock window.getComputedStyle
// Provides computed styles for components that need them
window.getComputedStyle = vi.fn(() => ({
  getPropertyValue: vi.fn(() => ''),
})) as any

// Suppress console errors/warnings in tests (optional)
// Uncomment if you want to suppress console output during tests
// const originalError = console.error
// beforeAll(() => {
//   console.error = (...args: any[]) => {
//     if (
//       typeof args[0] === 'string' &&
//       (args[0].includes('Warning:') || args[0].includes('Error:'))
//     ) {
//       return
//     }
//     originalError.call(console, ...args)
//   }
// })
//
// afterAll(() => {
//   console.error = originalError
// })

// Mock WebSocket
// Required for components that use WebSocket connections
// NOTE: Integration tests that use websocket-polyfill will override this
// Only set up mock if WebSocket hasn't been polyfilled already (check by looking for WebSocketPolyfill)
if (!global.WebSocket || (global.WebSocket as any).name !== 'WebSocketPolyfill') {
global.WebSocket = class WebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  readyState = WebSocket.CONNECTING
  url = ''
  protocol = ''
  extensions = ''
  binaryType: 'blob' | 'arraybuffer' = 'blob'

  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = typeof url === 'string' ? url : url.toString()
  }

  close() {}
  send() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true
  }
} as any
}

// Mock fetch API
// Required for components that make HTTP requests
global.fetch = vi.fn()

// Mock localStorage
// Required for components that use localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    get length() {
      return Object.keys(store).length
    },
    key: (index: number) => {
      const keys = Object.keys(store)
      return keys[index] || null
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
  configurable: true,
})

// Set default timezone for consistent test results
// Uncomment and set to a specific timezone if needed
// process.env.TZ = 'UTC'

// Setup MSW (Mock Service Worker) for API mocking in tests
setupMSW()

// Global mock for useWebSocketConnection hook
// This ensures components that use ConnectionStatusIndicator don't fail
// Individual tests can override this mock if needed
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocketConnection: vi.fn(() => ({
    status: {
      state: 'DISCONNECTED',
      isConnected: false,
      isConnecting: false,
      isReconnecting: false,
      isDisconnected: true,
    },
    connect: vi.fn(),
    disconnect: vi.fn(),
    client: {} as any,
  })),
  useWebSocket: vi.fn(() => ({
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    isSubscribed: vi.fn(() => false),
  })),
  useWebSocketEvent: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
  })),
}))

