/**
 * CommonJS/ESM Interop Helpers
 *
 * This module provides interop helper functions that are injected into
 * pre-bundled dependencies to fix _interopRequireDefault2 errors.
 */

export function _interopRequireDefault(obj: any) {
  return obj && obj.__esModule ? obj : { default: obj }
}

export function _interopRequireDefault2(obj: any) {
  return _interopRequireDefault(obj)
}

// Also make available globally for pre-bundled modules
if (typeof globalThis !== 'undefined') {
  (globalThis as any)._interopRequireDefault = _interopRequireDefault
  ;(globalThis as any)._interopRequireDefault2 = _interopRequireDefault2
}
if (typeof window !== 'undefined') {
  (window as any)._interopRequireDefault = _interopRequireDefault
  ;(window as any)._interopRequireDefault2 = _interopRequireDefault2
}

