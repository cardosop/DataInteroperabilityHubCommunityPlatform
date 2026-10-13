/**
 * Canonical API base-URL resolution for Node-side E2E helpers.
 *
 * Single source of truth — every fixture and spec that makes direct API
 * calls (auth, test-user setup, infrastructure-canary, security-headers)
 * MUST use this instead of re-deriving its own precedence chain. A
 * spec-level chain that disagrees with the login helpers is a split-brain
 * bug: the token is minted against one backend and presented to another,
 * surfacing as baffling 401s on endpoints that work minutes later (the
 * 2026-09-22 canary run hit exactly this when a spec-local chain fell
 * back to staging).
 *
 * Precedence:
 *   1. E2E_API_BASE_URL        — explicit runner contract (global-setup
 *                                writes it into .env.e2e for the Vite proxy).
 *   2. VITE_PROXY_TARGET       — the API the Vite proxy forwards to.
 *   3. VITE_API_BASE_URL       — only when absolute.
 *   4. localhost:8001 when E2E_WEB_PORT is set (docker-compose.test.yml
 *      publishes the test stack there), else localhost:8000.
 */

export function getApiBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  const base =
    env.E2E_API_BASE_URL ||
    (env.VITE_PROXY_TARGET
      ? `${env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
      : null) ||
    (env.VITE_API_BASE_URL?.startsWith('http')
      ? env.VITE_API_BASE_URL
      : null) ||
    `http://localhost:${env.E2E_WEB_PORT ? '8001' : '8000'}/api/v1`;
  // Validate eagerly — a malformed base must fail at the first API call
  // with a clear message, not degrade into `fetch('undefined/api/v1')`
  // style strings that explode as `TypeError: Invalid URL` mid-test.
  try {
    new URL(base);
  } catch {
    throw new Error(
      `getApiBaseUrl: resolved invalid API base URL '${base}'. ` +
        `Check E2E_API_BASE_URL / VITE_PROXY_TARGET / VITE_API_BASE_URL env vars.`
    );
  }
  return base;
}
