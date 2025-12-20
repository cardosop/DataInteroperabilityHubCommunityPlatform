/**
 * Vite Plugin: Patch Pre-bundled Interop Helpers
 *
 * This plugin patches Vite's pre-bundled dependencies using middleware
 * to intercept and patch files as they're served.
 */

import type { Plugin } from 'vite'
import type { Connect } from 'vite'

export function patchInteropPlugin(): Plugin {
  return {
    name: 'vite-plugin-patch-interop',
    enforce: 'post',
    configureServer(server) {
      // Intercept requests to pre-bundled dependency files
      // Must run early to catch all requests
      server.middlewares.use((req, res, next) => {
        const url = req.url || ''

        // Only patch pre-bundled dependency files
        if (url.includes('/node_modules/.vite/deps/') && (url.endsWith('.js') || url.includes('?v='))) {
          // Store original end function
          const originalEnd = res.end.bind(res)
          const chunks: Buffer[] = []

          // Intercept response
          const originalWrite = res.write.bind(res)
          res.write = function(chunk: any) {
            if (chunk) {
              chunks.push(Buffer.from(chunk))
            }
            return true
          } as any

          res.end = function(chunk?: any) {
            if (chunk) {
              chunks.push(Buffer.from(chunk))
            }

            // Combine all chunks
            let content = Buffer.concat(chunks).toString('utf-8')

            // Patch the content if it contains interop references
            // Check for bare identifier usage (not already wrapped)
            if (content.includes('_interopRequireDefault2') &&
                !content.includes('globalThis._interopRequireDefault2') &&
                !content.includes('window._interopRequireDefault2')) {

              // Replace all occurrences of _interopRequireDefault2 with global access
              // This is a more aggressive replacement that handles all cases
              content = content.replace(
                /\b_interopRequireDefault2\b/g,
                '(typeof globalThis !== "undefined" && globalThis._interopRequireDefault2 ? globalThis._interopRequireDefault2 : typeof window !== "undefined" && window._interopRequireDefault2 ? window._interopRequireDefault2 : function(obj) { return obj && obj.__esModule ? obj : { default: obj }; })'
              )

              // Also replace _interopRequireDefault
              content = content.replace(
                /\b_interopRequireDefault\b/g,
                '(typeof globalThis !== "undefined" && globalThis._interopRequireDefault ? globalThis._interopRequireDefault : typeof window !== "undefined" && window._interopRequireDefault ? window._interopRequireDefault : function(obj) { return obj && obj.__esModule ? obj : { default: obj }; })'
              )
            }

            // Send patched content
            res.setHeader('Content-Length', Buffer.byteLength(content))
            originalEnd(content)
          }
        } else {
          next()
        }
      })
    },
  }
}

