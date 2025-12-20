/**
 * MSW Server Setup for Tests
 *
 * Sets up Mock Service Worker server for Node.js test environment.
 */

import { setupServer } from 'msw/node'
import { defaultHandlers } from './handlers'

/**
 * MSW server instance for tests
 */
export const server = setupServer(...defaultHandlers)

/**
 * Setup MSW server before all tests
 */
export function setupMSW() {
  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'warn' })
  })

  afterEach(() => {
    server.resetHandlers()
  })

  afterAll(() => {
    server.close()
  })
}

