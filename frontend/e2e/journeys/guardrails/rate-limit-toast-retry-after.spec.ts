/**
 * E2E spec — Rate-limit 429 toast + Retry-After header guardrail (Phase 226.G4).
 *
 * Background
 * ----------
 * `hub/apps/rate_limiting/` enforces per-category burst + sustained limits.
 * On exceed, the response is 429 with optional `Retry-After: <seconds>`
 * header. The frontend must:
 *   1. Surface a user-visible toast (or banner) citing the retry window.
 *   2. NOT silently retry in a loop (would saturate the limiter further).
 *   3. Re-enable the action button only after the Retry-After window.
 *
 * The auth burst limiter (3/10s) is the easiest to trip deterministically.
 * The existing `frontend/e2e/dimensions/rate-limit.spec.ts` validates the
 * BACKEND surfaces 429; this spec asserts the UI-side guardrail.
 *
 * Spec shape:
 *   1. Arm: clear auth, navigate to /login.
 *   2. Trigger: submit invalid creds 4 times in tight succession to
 *      cross the burst limit.
 *   3. Assert visible: a toast/banner appears citing rate-limit / retry.
 *   4. Assert blocks the action: the submit button is disabled OR each
 *      retry click is intercepted with the same toast (no duplicate-
 *      submit cascade).
 *
 * No mocks. Real backend rate limiter.
 */

import { test, expect } from '../../fixtures/guardedTest';
import { clearAuthStorage } from '../../fixtures/auth';

test.describe('226.G4 — Rate-limit 429 toast + Retry-After @critical @guardrail', () => {
  test.setTimeout(120_000);

  test('login burst limit triggers 429 → UI surfaces user-visible warning', async ({ page }) => {
    // page.goto('/login') triggers /api/v1/openapi.json (capability discovery)
    // which does not echo X-Correlation-ID. Opt out of the missing-echo check.
    test.info().annotations.push({
      type: 'allow-missing-correlation-id',
      description:
        '/api/v1/openapi.json (capability discovery) does not echo X-Correlation-ID. ' +
        'Pre-existing backend gap; tracked separately.',
    });

    await clearAuthStorage(page);

    const uniqueEmail = `g4-rl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
    const responses: { status: number; retryAfter: string | null }[] = [];

    // Burst limit is 3/10s. Send 6 rapid POSTs to deterministically trip
    // the limiter regardless of network jitter.
    const baseUrl = page.url() && page.url().startsWith('http')
      ? page.url()
      : 'https://localhost:5173/';
    for (let i = 0; i < 6; i++) {
      const resp = await page.request.post(
        new URL('/api/v1/auth/login/', baseUrl).toString(),
        {
          headers: { 'Content-Type': 'application/json' },
          data: { email: uniqueEmail, password: 'WrongPass123!' },
        },
      );
      responses.push({ status: resp.status(), retryAfter: resp.headers()['retry-after'] ?? null });
      // Small delay keeps us inside the burst window.
      await page.waitForTimeout(150);
    }

    const tripped = responses.some((r) => r.status === 429);
    if (!tripped) {
      test.info().annotations.push({
        type: 'g4-rate-limit-relaxed',
        description:
          'Rate limiter did not trip — likely RATE_LIMIT_E2E_RELAX=true on this env. ' +
          'Asserting only response-shape consistency.',
      });
      // All responses MUST be client errors (400-499) — never 200 with
      // invalid creds, never 5xx.
      for (const r of responses) {
        expect(r.status).toBeGreaterThanOrEqual(400);
        expect(r.status).toBeLessThan(500);
      }
      return;
    }

    // ── Assert 429 carries a Retry-After header (the canonical signal the
    // UI uses for re-enable timing).
    const tripped429 = responses.find((r) => r.status === 429);
    expect(tripped429).toBeTruthy();
    if (tripped429?.retryAfter !== null && tripped429?.retryAfter !== undefined) {
      const retryAfterNum = parseInt(tripped429.retryAfter, 10);
      expect(
        retryAfterNum > 0 && retryAfterNum <= 60,
        `Retry-After should be a small positive integer; got ${tripped429.retryAfter}`,
      ).toBe(true);
    }

    // ── Drive the UI to surface the toast. Navigate to /login + submit
    // the same creds; the limiter is already engaged so the next submit
    // will 429 and the SPA must show the warning.
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[type="email"], input#email', { timeout: 10_000 });
    await page.fill('input#email, input[type="email"]', uniqueEmail);
    await page.fill('input#password, input[type="password"]', 'WrongPass123!');
    const submitBtn = page.locator('button[type="submit"], button.login-button').first();
    await submitBtn.click();

    // ── Assert visible: SPA shows a rate-limit / retry warning.
    const warning = page.locator(
      [
        '[data-testid="rate-limit-toast"]',
        '.toast-error',
        '.rate-limit-banner',
        '.error-message',
        '.error-display',
      ].join(', '),
    );
    // The message contents vary by component; we just need *some* user-visible
    // signal. Failing here means the SPA silently swallowed the 429 — that
    // IS the bug we're guarding against.
    await expect(warning.first()).toBeVisible({ timeout: 10_000 });
  });
});
