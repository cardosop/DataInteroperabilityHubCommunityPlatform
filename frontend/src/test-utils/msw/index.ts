/**
 * MSW (Mock Service Worker) Exports
 *
 * Centralized exports for MSW setup and utilities.
 * Only exports server for test environment to avoid browser-only code.
 */

export * from './handlers'
export * from './server'
// Browser exports are available separately - import from './msw/browser' if needed
// Not exported here to avoid issues in Node.js test environment

