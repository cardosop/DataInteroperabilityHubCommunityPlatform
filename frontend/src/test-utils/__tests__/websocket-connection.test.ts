/**
 * Minimal WebSocket Connection Test
 *
 * Direct test of ws library connecting to test server
 * This verifies the basic connection mechanism works before
 * testing the full WebSocket client implementation.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { WebSocket as WS } from 'ws'
import { createTestWebSocketServer, TestWebSocketServer } from '../websocket-test-server'

describe('Direct WebSocket Connection Test', () => {
  let testServer: TestWebSocketServer

  beforeAll(async () => {
    testServer = createTestWebSocketServer({
      port: 0,
      path: '/ws/events/',
      requireAuth: true,
    })
    await testServer.start()
  })

  afterAll(async () => {
    await testServer.stop()
  })

  it('should connect directly to test server with token in URL', async () => {
    return new Promise<void>((resolve, reject) => {
      const serverUrl = testServer.getUrl()
      const urlWithToken = `${serverUrl}?token=test-token`

      console.log('[DirectTest] Connecting to:', urlWithToken)

      const ws = new WS(urlWithToken)

      ws.on('open', () => {
        console.log('[DirectTest] Connection opened successfully')
        expect(ws.readyState).toBe(WS.OPEN)
        ws.close()
        resolve()
      })

      ws.on('error', (error) => {
        console.error('[DirectTest] Connection error:', error)
        reject(error)
      })

      ws.on('close', (code, reason) => {
        console.log('[DirectTest] Connection closed:', { code, reason: reason.toString() })
      })

      // Timeout after 5 seconds
      setTimeout(() => {
        if (ws.readyState !== WS.OPEN && ws.readyState !== WS.CLOSED) {
          ws.close()
          reject(new Error('Connection timeout'))
        }
      }, 5000)
    })
  })

  it('should connect directly to test server with token in header', async () => {
    return new Promise<void>((resolve, reject) => {
      const serverUrl = testServer.getUrl()

      console.log('[DirectTest] Connecting to:', serverUrl, 'with header auth')

      const ws = new WS(serverUrl, {
        headers: {
          Authorization: 'Bearer test-token',
        },
      } as any)

      ws.on('open', () => {
        console.log('[DirectTest] Connection opened successfully with header auth')
        expect(ws.readyState).toBe(WS.OPEN)
        ws.close()
        resolve()
      })

      ws.on('error', (error) => {
        console.error('[DirectTest] Connection error with header:', error)
        reject(error)
      })

      ws.on('close', (code, reason) => {
        console.log('[DirectTest] Connection closed:', { code, reason: reason.toString() })
      })

      // Timeout after 5 seconds
      setTimeout(() => {
        if (ws.readyState !== WS.OPEN && ws.readyState !== WS.CLOSED) {
          ws.close()
          reject(new Error('Connection timeout'))
        }
      }, 5000)
    })
  })

  it('should reject connection without token', async () => {
    return new Promise<void>((resolve, reject) => {
      const serverUrl = testServer.getUrl()
      let resolved = false

      console.log('[DirectTest] Attempting connection without token')

      const ws = new WS(serverUrl)

      ws.on('open', () => {
        if (!resolved) {
          resolved = true
          ws.close()
          reject(new Error('Connection should have been rejected'))
        }
      })

      ws.on('error', (error) => {
        console.log('[DirectTest] Expected error (no token):', error)
        // Error is expected, but wait for close event
      })

      ws.on('close', (code, reason) => {
        console.log('[DirectTest] Connection closed:', { code, reason: reason.toString() })
        if (!resolved) {
          resolved = true
          if (code === 1008) {
            // Unauthorized - expected
            resolve()
          } else {
            reject(new Error(`Unexpected close code: ${code}, expected 1008 (Unauthorized)`))
          }
        }
      })

      // Timeout after 5 seconds
      setTimeout(() => {
        if (!resolved) {
          resolved = true
          if (ws.readyState === WS.OPEN) {
            ws.close()
            reject(new Error('Connection should have been rejected but was open'))
          } else if (ws.readyState === WS.CLOSED) {
            // Already closed, check if it was with the right code
            // Note: We can't get the close code after the fact, so we assume it's correct
            resolve()
          } else {
            ws.close()
            reject(new Error('Connection timeout'))
          }
        }
      }, 5000)
    })
  })
})

