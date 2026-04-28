/**
 * `ensureE2eSubscription` — best-effort prime of the E2E test user's tenant
 * subscription + KYC status before any write call.
 *
 * Background — why this exists
 * ----------------------------
 * Meshant's billing middleware blocks asset/contract/dataset POSTs with
 * `403 subscription_inactive` when the tenant has no active subscription.
 * For E2E, the canonical seeder is
 * `POST /api/v1/test/ensure-e2e-subscription/` (`hub/apps/api/views.py:
 * 424-453`), gated by the `require_e2e_token` decorator (X-E2E-Token shared
 * secret) + `E2E_EMAILS` allow-list + ENVIRONMENT in (test, staging, debug).
 *
 * Existing fixtures (`api-assets.ts`) call this endpoint *reactively* after
 * a 403 fires. New 226.G specs that POST directly via `page.request.post`
 * benefit from a *proactive* call — saves a round-trip and avoids
 * occasional flakes when the in-flight retry races with parallel workers.
 *
 * Idempotent: the backend implementation just calls
 * `ensure_e2e_tenant_ready(request.user.tenant)` which is idempotent. Multiple
 * calls per test process are harmless.
 *
 * Failure modes — best-effort by design
 * -------------------------------------
 *   - 404: helper not exposed on this env (production, or test secret
 *     missing). Caller should proceed; the actual create call will fail
 *     with a useful error.
 *   - 403: user not in E2E_EMAILS. Same — let the create's error speak.
 *   - 5xx: backend trouble; we don't want to mask it by failing pre-flight.
 *
 * Pure side-effect — returns void. Use as the first call after `loginViaApi`.
 */

import type { Page } from '@playwright/test';
import { e2eTestHeaders } from './e2e-token';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

/**
 * Prime the test user's tenant subscription + KYC. Best-effort —
 * never throws.
 *
 * @param page Playwright page (used to issue the request via the page's
 *             request context; inherits proxy + cookies for free).
 * @param accessToken Bearer token for the E2E user. Required because the
 *             helper is `permission_classes = [IsAuthenticated]`.
 */
export async function ensureE2eSubscription(page: Page, accessToken: string): Promise<void> {
  try {
    await page.request.post(`${API_BASE}/test/ensure-e2e-subscription/`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        ...e2eTestHeaders(),
      },
    });
  } catch {
    // Best-effort. The downstream POST will surface the real error if the
    // tenant remains unprimed.
  }
}
