/**
 * E2E Test: JOURNEY-AUTH-003 — User Resets Password
 *
 * Journey: User Resets Password
 * Persona: Visitor, any registered user
 * Use cases: UC-AUTH-003
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Per-journey structure: Success, Failure, Edge. Shared steps from fixtures/auth-journey-steps.
 * Real backend only; password reset confirmation relies on MailHog (no mocks).
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import { runJOURNEY_AUTH_003_Success } from '../../fixtures/auth-journey-steps';

const MAILHOG_BASE_URL = process.env.MAILHOG_URL || 'http://localhost:8025';
const WORKER_HEALTH_URL = process.env.WORKER_HEALTH_URL || 'http://localhost:8087/healthz';

test.describe('JOURNEY-AUTH-003: User Resets Password @critical', () => {
  // Allow loginUser rate-limit retries (up to 4×65s) after password reset confirm when suite runs many auth tests
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('visitor requests password reset and confirms via email link', async ({ page }) => {
      // External-target safety: when running against staging/prod, MailHog is
      // typically not deployed and MAILHOG_URL must be explicitly pointed at a
      // reachable email-sink. If MAILHOG_URL is left at its localhost default
      // while PLAYWRIGHT_BASE_URL is non-localhost, a developer-side MailHog
      // container running for *other* tests would falsely report reachable —
      // the test would then submit the form against staging, wait 120s for an
      // email that never arrives in the local sink, and time out instead of
      // skipping cleanly. Detect that mismatch up front and skip with a clear
      // remediation message.
      const isExternalTarget = !!process.env.PLAYWRIGHT_BASE_URL?.match(
        /^https?:\/\/(?!localhost|127\.)/
      );
      const isMailhogOverrideSet = !!process.env.MAILHOG_URL;
      const isMailhogLocalhost = /^https?:\/\/(localhost|127\.)/i.test(MAILHOG_BASE_URL);
      test.skip(
        isExternalTarget && !isMailhogOverrideSet && isMailhogLocalhost,
        `Running against external target (${process.env.PLAYWRIGHT_BASE_URL}) ` +
          `but MAILHOG_URL is not set — defaulting to ${MAILHOG_BASE_URL}. ` +
          `Staging emails will not be delivered to a local sink, so the email ` +
          `interception step would hang for the full test budget. Set ` +
          `MAILHOG_URL=https://<staging-mailhog-host> to run, or accept the ` +
          `skip (the password-reset feature itself is exercised by the ` +
          `Failure / Edge tests in this file).`
      );

      let mailhogReachable = false;
      let workerReachable = false;
      // Retry probes once — under parallel E2E load the first attempt can fail
      // with a transient connection error even though the services are healthy.
      for (let attempt = 0; attempt < 2 && !mailhogReachable; attempt++) {
        try {
          const probe = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=1`, {
            signal: AbortSignal.timeout(5000),
          });
          if (probe.ok) mailhogReachable = true;
        } catch {
          if (attempt === 0) await new Promise((r) => setTimeout(r, 2000));
        }
      }
      for (let attempt = 0; attempt < 2 && !workerReachable; attempt++) {
        try {
          const workerProbe = await fetch(WORKER_HEALTH_URL, {
            signal: AbortSignal.timeout(5000),
          });
          if (workerProbe.ok) workerReachable = true;
        } catch {
          if (attempt === 0) await new Promise((r) => setTimeout(r, 2000));
        }
      }
      // Skip when MailHog is unavailable. The success path MUST intercept the
      // password-reset email to extract the token — there is no API shortcut.
      // On external targets (staging), MailHog is typically not deployed; set
      // MAILHOG_URL to a reachable MailHog instance if available.
      test.skip(
        !mailhogReachable,
        isExternalTarget
          ? `MailHog not reachable at ${MAILHOG_BASE_URL}. ` +
            `Running against external target (${process.env.PLAYWRIGHT_BASE_URL}); ` +
            `set MAILHOG_URL to the staging MailHog endpoint, or skip this test ` +
            `(password reset works — the E2E just cannot intercept real emails).`
          : `MailHog not reachable at ${MAILHOG_BASE_URL}. Password reset requires MailHog for email delivery. ` +
            `Start: docker compose -f docker-compose.test.yml up -d mailhog-test`
      );
      test.skip(
        !workerReachable,
        `Worker not reachable at ${WORKER_HEALTH_URL}. Password reset requires worker to process email jobs. ` +
          `Start: docker compose -f docker-compose.test.yml up -d worker-service-test`
      );
      await runJOURNEY_AUTH_003_Success(page);
    });
  });

  test.describe('Failure', () => {
    test('password reset page shows generic success even when email unknown', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/password-reset', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        await page.getByRole('link', { name: /Forgot your password/i }).click();
        await page.waitForURL((url) => url.pathname.includes('password-reset'), { timeout: 5000 });
      }
      // CapabilityRoute blocks with LoadingSpinner until capabilities load (up to 30s)
      const resetOrUnavailable = page
        .getByRole('heading', { name: /Reset password/i })
        .or(page.locator('.unavailable-page, [data-testid="unavailable-page"] h1'));
      await expect(resetOrUnavailable.first()).toBeVisible({ timeout: 35_000 });
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Password reset unavailable (capabilities/schema). JOURNEY-AUTH-003 requires password reset to be enabled. ' +
            'Enable password reset in deployment capabilities or schema.'
        );
      }
      await page.fill('input#email', 'nonexistent@example.com');
      await page.click('button[type="submit"]');
      // Backend returns generic success for unknown emails (security); API can be slow under load
      await expect(page.locator('.success-message')).toContainText(
        /If the email exists|success|sent/i,
        { timeout: 20_000 }
      );
    });

    test('confirm page shows error for invalid or expired token', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/password-reset/confirm?token=00000000-0000-0000-0000-000000000000', {
        waitUntil: 'domcontentloaded',
      });
      // CapabilityRoute blocks with LoadingSpinner until capabilities load (up to 30s)
      await expect(
        page.getByRole('heading', { name: /Set a new password/i }).or(page.locator('.unavailable-page, [data-testid="unavailable-page"] h1'))
      ).toBeVisible({ timeout: 35_000 });
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Password reset confirm unavailable (capabilities/schema). JOURNEY-AUTH-003 requires password reset to be enabled. ' +
            'Enable password reset in deployment capabilities or schema.'
        );
      }
      await page.fill('input#new_password', 'NewSecurePass123');
      await page.click('button[type="submit"]');
      await page.locator('.error-message, .success-message').first().waitFor({ timeout: 25_000 });
      const hasError = (await page.locator('.error-message').count()) > 0;
      expect(hasError).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('password-reset page renders a meaningful heading (not a blank page)', async ({ page }) => {
      // Edge: verify the page renders a recognisable heading regardless of whether password-reset
      // is enabled or disabled. A blank/empty render (no heading) is the regression being guarded.
      await clearAuthStorage(page);
      await page.goto('/password-reset', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        await page.getByRole('link', { name: /Forgot your password/i }).click();
        await page.waitForURL((url) => url.pathname.includes('password-reset'), { timeout: 5000 });
      }
      // CapabilityRoute blocks with LoadingSpinner until capabilities load (up to 30s)
      const resetOrUnavailable = page
        .getByRole('heading', { name: /Reset password/i })
        .or(page.locator('.unavailable-page, [data-testid="unavailable-page"] h1'));
      await expect(resetOrUnavailable.first()).toBeVisible({ timeout: 35_000 });
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Password reset unavailable (capabilities/schema). JOURNEY-AUTH-003 requires password reset to be enabled. ' +
            'Enable password reset in deployment capabilities or schema.'
        );
      }
      expect(page.url()).toContain('password-reset');
      // Verify the heading text is non-empty (not a blank render)
      const headingText = await resetOrUnavailable.first().textContent();
      expect((headingText ?? '').trim().length).toBeGreaterThan(0);
      // The form must have an email input — a blank-page regression would omit it
      await expect(page.locator('input#email')).toBeVisible({ timeout: 5000 });
    });

    test('password reset form with empty email stays on page or shows validation', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/password-reset', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        await page.getByRole('link', { name: /Forgot your password/i }).click();
        await page.waitForURL((url) => url.pathname.includes('password-reset'), { timeout: 5000 });
      }
      const heading = page
        .getByRole('heading', { name: /Reset password/i })
        .or(page.locator('.unavailable-page, [data-testid="unavailable-page"] h1'));
      await expect(heading.first()).toBeVisible({ timeout: 35_000 });
      if (page.url().includes('/unavailable')) {
        return;
      }
      await page.fill('input#email', '');
      await page.locator('button[type="submit"]').click();
      await page.waitForTimeout(500);
      const stillOnReset = page.url().includes('password-reset');
      const hasValidation =
        (await page.locator('input#email:invalid').count()) > 0 ||
        (await page.locator('.error-message').count()) > 0;
      expect(stillOnReset || hasValidation).toBe(true) /* acceptable states */;
    });
  });
});
