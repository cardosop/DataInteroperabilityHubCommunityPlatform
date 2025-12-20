/**
 * MSW Browser Setup for Development
 *
 * Sets up Mock Service Worker for browser environment (development mode).
 */

import { setupWorker } from 'msw/browser'
import { defaultHandlers } from './handlers'

/**
 * MSW worker instance for browser
 */
export const worker = setupWorker(...defaultHandlers)

/**
 * Start MSW worker in browser
 *
 * Call this function in your main.tsx or App.tsx during development.
 *
 * @example
 * ```tsx
 * // In main.tsx
 * if (import.meta.env.DEV) {
 *   startMSW().then(() => {
 *     ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
 *   })
 * } else {
 *   ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
 * }
 * ```
 */
export async function startMSW() {
  if (typeof window === 'undefined') {
    return
  }

  // Only start MSW in development mode
  if (!import.meta.env.DEV) {
    console.warn('[MSW] Mock Service Worker is only available in development mode')
    return
  }

  // Check if MSW is enabled via environment variable
  const mswEnabled = import.meta.env.VITE_MSW_ENABLED === 'true'

  if (!mswEnabled) {
    console.log('[MSW] Mock Service Worker is disabled. Set VITE_MSW_ENABLED=true to enable.')
    return
  }

  try {
    await worker.start({
      onUnhandledRequest: 'warn',
      serviceWorker: {
        url: '/mockServiceWorker.js',
      },
    })
    console.log('[MSW] Mock Service Worker started successfully')
  } catch (error) {
    console.error('[MSW] Failed to start Mock Service Worker:', error)
    console.warn('[MSW] Make sure to run: npx msw init public/ --save')
  }
}

/**
 * Stop MSW worker
 */
export function stopMSW() {
  worker.stop()
}

