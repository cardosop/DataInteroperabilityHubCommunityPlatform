/**
 * Shared-secret header for /api/v1/test/ensure-e2e-* endpoints.
 *
 * The Django-side @require_e2e_token decorator compares the X-E2E-Token
 * header against settings.E2E_TEST_SECRET via hmac.compare_digest; an
 * empty or wrong header returns 404. We read the secret from the
 * E2E_TEST_SECRET environment variable — the same value AWS Secrets
 * Manager publishes into the backend pod via ExternalSecrets on staging.
 *
 * Usage:
 *     import { e2eTestHeaders } from '../fixtures/e2e-token';
 *     await fetch(url, { headers: { 'Content-Type': 'application/json', ...e2eTestHeaders() } });
 *
 * See docs/e2e-setup.md for provisioning the secret locally / in CI.
 */

export const E2E_TOKEN_HEADER = 'X-E2E-Token';

/**
 * Returns the header object to merge into ensure_e2e_* requests.
 * Always returns the header (even if the env var is empty) so that
 * misconfiguration surfaces as a 404 from the backend rather than
 * being silently skipped at the test harness.
 */
export function e2eTestHeaders(): Record<string, string> {
  const token = process.env.E2E_TEST_SECRET ?? '';
  return { [E2E_TOKEN_HEADER]: token };
}
