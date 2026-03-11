/**
 * E2E brand constant for design-system tests.
 * Configurable via E2E_APP_NAME or VITE_APP_NAME env vars; default 'Meshant'.
 * No hardcoded brand in specs — use this constant for assertions.
 */
export const E2E_APP_NAME =
  process.env.E2E_APP_NAME || process.env.VITE_APP_NAME || 'Meshant';
