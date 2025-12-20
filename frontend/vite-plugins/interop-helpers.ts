/**
 * Vite Plugin: CommonJS/ESM Interop Helpers
 *
 * Injects interop helper functions to fix _interopRequireDefault2 errors
 * that occur when Vite pre-bundles CommonJS dependencies.
 *
 * This plugin ensures the interop helpers are available globally before
 * any module code executes.
 */

import type { Plugin } from 'vite'

export function interopHelpersPlugin(): Plugin {
  return {
    name: 'vite-plugin-interop-helpers',
    enforce: 'pre',
    transformIndexHtml: {
      enforce: 'pre',
      transform(html) {
        // Inject interop helpers at the very beginning of the HTML
        // This ensures they're available before any module code runs
        const interopHelpers = `
          <script>
            // CommonJS/ESM interop helpers
            // These must be defined before any module code executes
            (function() {
              var helper = function(obj) {
                return obj && obj.__esModule ? obj : { default: obj };
              };
              // Define on all global objects
              if (typeof globalThis !== 'undefined') {
                globalThis._interopRequireDefault = globalThis._interopRequireDefault || helper;
                globalThis._interopRequireDefault2 = globalThis._interopRequireDefault2 || helper;
              }
              if (typeof window !== 'undefined') {
                window._interopRequireDefault = window._interopRequireDefault || helper;
                window._interopRequireDefault2 = window._interopRequireDefault2 || helper;
              }
              // Make available as global variables using Object.defineProperty
              // This works even in strict mode
              try {
                Object.defineProperty(globalThis, '_interopRequireDefault', {
                  value: helper,
                  writable: true,
                  configurable: true,
                });
                Object.defineProperty(globalThis, '_interopRequireDefault2', {
                  value: helper,
                  writable: true,
                  configurable: true,
                });
              } catch (e) {
                // Fallback if defineProperty fails
              }
            })();
          </script>
        `
        return html.replace('<head>', `<head>${interopHelpers}`)
      },
    },
    // Transform hook removed - using esbuildOptions.inject instead
    // This provides helpers as imports, avoiding duplicate declarations
  }
}

