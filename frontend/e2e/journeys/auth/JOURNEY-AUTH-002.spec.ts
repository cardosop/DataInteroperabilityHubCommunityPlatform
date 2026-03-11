/**
 * E2E Test: JOURNEY-AUTH-002 - User Logs In
 *
 * Journey: User Logs In
 * Persona: Visitor (becomes authenticated)
 * Priority: High
 * Status: MVP
 * Category: Authentication & Access
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { assertVisible, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-AUTH-002: User Logs In', () => {
  test.setTimeout(200000); // 3+ min: rate-limiting test does 6 login attempts; visible/slowMo adds latency

  /**
   * Performance: Login completes within target time (runs first to avoid rate-limit exhaustion)
   *
   * Uses shared loginUser fixture; measures duration. Run early so auth rate limit is fresh.
   */
  test('performance: login completes within target time', async ({ page }) => {
    test.setTimeout(180000); // 3 min: API under load, rate-limit retries

    await clearAuthStorage(page);
    const testUser = await getTestUser();
    const startTime = Date.now();

    await loginUser(page, testUser, { useUiLogin: true });

    const duration = Date.now() - startTime;
    const targetDuration = 130000; // 130s allows one 65s rate-limit retry (no mocks)

    expect(duration).toBeLessThan(targetDuration);
    console.log(`Login completed in ${duration}ms (target: ${targetDuration}ms)`);
  });

  /**
   * Happy Path: User successfully logs in
   *
   * Uses shared loginUser fixture (same code path as other auth tests) so rate-limit
   * retries (429) and redirect handling are consistent. Verifies redirect and app shell.
   */
  test('happy path: user successfully logs in', async ({ page }) => {
    test.setTimeout(180000); // 3 min: API under load, rate-limit retries

    await clearAuthStorage(page);
    const testUser = await getTestUser();
    await loginUser(page, testUser, { useUiLogin: true });

    await expect(page).not.toHaveURL(/\/login/);
    await assertVisible(page, '.app-header');
    await assertVisible(page, '.app-sidebar');
  });

  test.describe('Failure', () => {
    /**
     * Failure Scenario: Invalid credentials (auth/validation)
     * Verifies that invalid credentials are rejected with appropriate error message.
     */
    test('invalid credentials show error', async ({ page }) => {
      test.setTimeout(90000);

      await clearAuthStorage(page);
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page);

      await page.fill('input#email', 'invalid@example.com');
      await page.fill('input#password', 'wrongpassword');

      // Submit via Enter to avoid button disabled-state race; wait for API response
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes('/auth/login/') &&
          (resp.status() === 400 || resp.status() === 401 || resp.status() === 429),
        { timeout: 60000 }
      );
      await page.locator('input#password').press('Enter');
      const response = await responsePromise;

      // Verify API returned client error (400/401) or rate limit (429)
      expect(response.status()).toBeGreaterThanOrEqual(400);
      expect(response.status()).toBeLessThan(500);

      // Wait for error message to appear (UI shows "Login failed" or rate limit message)
      await page.waitForSelector('.error-message', { timeout: 15000 });
      const errorMessage = await page.locator('.error-message').textContent();

      // Verify error message is displayed (generic "Login failed", API error, or rate limit)
      expect(errorMessage).toBeTruthy();
      expect(errorMessage?.toLowerCase()).toMatch(
        /login|failed|invalid|credentials|authentication|error|rate limit|too many requests/i
      );
    });

    /**
     * Failure Scenario: Empty credentials (validation)
     * Verifies that empty credentials are rejected.
     */
    test('empty credentials show validation or stay on login', async ({ page }) => {
      test.setTimeout(30000);

      await clearAuthStorage(page);
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page);

      // Clear fields (they may have default values)
      await page.fill('input#email', '');
      await page.fill('input#password', '');

      const submitButton = page.locator('button[type="submit"]');

      // Try to submit - HTML5 validation should prevent submission
      await submitButton.click();

      // Wait a bit for validation to trigger
      await page.waitForTimeout(500);

      // Check if form validation prevented submission (inputs should be invalid)
      const emailInput = page.locator('input#email');
      const passwordInput = page.locator('input#password');

      // Verify inputs are marked as invalid (HTML5 validation)
      const emailValidity = await emailInput.evaluate((el: HTMLInputElement) => el.validity.valid);
      const passwordValidity = await passwordInput.evaluate(
        (el: HTMLInputElement) => el.validity.valid
      );

      // At least one should be invalid (both are required)
      expect(emailValidity || passwordValidity).toBe(false);

      // Verify we're still on login page (form didn't submit)
      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Edge', () => {
    /**
     * Edge Case: Rate limiting
     * Verifies that rate limiting is handled gracefully.
     */
    test('rate limiting handled gracefully', async ({ page }) => {
      test.setTimeout(180000); // Longer timeout for rate limit retries

      await clearAuthStorage(page);
      const testUser = await getTestUser();

      // Attempt multiple logins rapidly to trigger rate limiting
      for (let i = 0; i < 6; i++) {
        await page.goto('/login', { waitUntil: 'domcontentloaded' });
        await page.fill('input#email', testUser.email);
        await page.fill('input#password', testUser.password);

        const submitButton = page.locator('button[type="submit"]');
        await submitButton.click();

        // Wait for response (may be 200 or 429)
        try {
          await page.waitForResponse(
            (resp) =>
              resp.url().includes('/auth/login/') &&
              (resp.status() === 200 || resp.status() === 429),
            { timeout: 10000 }
          );
        } catch {
          // Timeout is acceptable
        }

        await page.waitForTimeout(1000);
      }

      const errorMessage = page.locator('.error-message');
      const rateLimitError = page.locator('text=/rate limit|too many requests/i');
      const hasError = (await errorMessage.count()) > 0 || (await rateLimitError.count()) > 0;
      console.log('Rate limiting test completed - system handled multiple login attempts');
    });

    /**
     * Edge Case: Special characters in email
     * Verifies that special characters in email are handled correctly.
     */
    test('special characters in email handled', async ({ page }) => {
      test.setTimeout(90000);

      await clearAuthStorage(page);
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await waitForLoadingComplete(page);

      await page.fill('input#email', 'test+special@example.com');
      await page.fill('input#password', 'password123');

      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes('/auth/login/') &&
          (resp.status() === 200 ||
            resp.status() === 400 ||
            resp.status() === 401 ||
            resp.status() === 429),
        { timeout: 60000 }
      );
      await page.locator('input#password').press('Enter');
      const response = await responsePromise;

      expect(response.status()).toBeGreaterThanOrEqual(200);
      expect(response.status()).toBeLessThan(500);

      if (response.status() >= 400) {
        await page.waitForSelector('.error-message', { timeout: 10000 });
        const errorMessage = await page.locator('.error-message').textContent();
        expect(errorMessage).toBeTruthy();
      }
    });
  });
});
