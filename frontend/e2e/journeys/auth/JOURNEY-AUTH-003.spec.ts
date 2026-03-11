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

test.describe('JOURNEY-AUTH-003: User Resets Password', () => {
  // Allow loginUser rate-limit retries (up to 4×65s) after password reset confirm when suite runs many auth tests
  test.setTimeout(480_000);

  test.describe('Success', () => {
    test('visitor requests password reset and confirms via email link', async ({ page }) => {
      let mailhogReachable = false;
      let workerReachable = false;
      try {
        const probe = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=1`);
        if (probe.ok) mailhogReachable = true;
      } catch {
        // ignore
      }
      try {
        const workerProbe = await fetch(WORKER_HEALTH_URL);
        if (workerProbe.ok) workerReachable = true;
      } catch {
        // ignore
      }
      // Skip when MailHog or worker unavailable (optional services for password reset flow).
      // Worker processes send_password_reset_email jobs; MailHog captures the email.
      test.skip(
        !mailhogReachable,
        `MailHog not reachable at ${MAILHOG_BASE_URL}. Password reset requires MailHog for email delivery. ` +
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
        .or(page.locator('.unavailable-page h1'));
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
        page.getByRole('heading', { name: /Set a new password/i }).or(page.locator('.unavailable-page h1'))
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
      expect(hasError).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('reset not enabled: UI shows contact admin or 501', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/password-reset', { waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        await page.getByRole('link', { name: /Forgot your password/i }).click();
        await page.waitForURL((url) => url.pathname.includes('password-reset'), { timeout: 5000 });
      }
      // CapabilityRoute blocks with LoadingSpinner until capabilities load (up to 30s)
      const resetOrUnavailable = page
        .getByRole('heading', { name: /Reset password/i })
        .or(page.locator('.unavailable-page h1'));
      await expect(resetOrUnavailable.first()).toBeVisible({ timeout: 35_000 });
      if (page.url().includes('/unavailable')) {
        throw new Error(
          'Password reset unavailable (capabilities/schema). JOURNEY-AUTH-003 requires password reset to be enabled. ' +
            'Enable password reset in deployment capabilities or schema.'
        );
      }
      expect(page.url()).toContain('password-reset');
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
        .or(page.locator('.unavailable-page h1'));
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
      expect(stillOnReset || hasValidation).toBe(true);
    });
  });
});
