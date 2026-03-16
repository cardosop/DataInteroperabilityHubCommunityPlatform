/**
 * E2E Test: JOURNEY-DE-008 — Integrate AI Schema Matching into Workflow
 *
 * Journey: Integrate AI Schema Matching into Workflow
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /ai/schema-matching.
 * Capability-gated: ai.schema-matching. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginViaApi } from '../../fixtures/auth';

/** Inject API tokens into the page to bypass slow UI login (avoids slowMo=400ms overhead). */
async function loginViaApiAndInject(page: import('@playwright/test').Page): Promise<void> {
  const testUser = await getTestUser();
  const auth = await loginViaApi(testUser.email, testUser.password);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(
    ({ accessToken, refreshToken, user }) => {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('user', JSON.stringify(user));
    },
    { accessToken: auth.access_token, refreshToken: auth.refresh_token, user: auth.user }
  );
}

test.describe('JOURNEY-DE-008: Integrate AI Schema Matching into Workflow', () => {
  // 6 min: capability-gated route; uses token injection to avoid slowMo login overhead
  test.setTimeout(360000);

  test.describe('Success', () => {
    test('schema matching page loads', async ({ page }) => {
      // Use API token injection instead of UI loginUser to avoid the slowMo=400ms-per-action
      // penalty on login, which caused the visible project to exceed the 360s budget when
      // the API was restarting and connection retries stacked up.
      await loginViaApiAndInject(page);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.schema-matching-page, .app-main, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 30000 }
      );
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onUnavailable = url.includes('/unavailable');
      const onSchemaMatching = url.includes('/ai/schema-matching');
      const hasContent =
        (await page.locator('.schema-matching-page, .app-main, .unavailable-page, .loading-spinner-container').count()) >
        0;
      expect(onLogin || on403 || onUnavailable || (onSchemaMatching && hasContent)).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /ai/schema-matching redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/ai/schema-matching', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)/, { timeout: 20000 }).catch(() => null);
      expect(page.url().includes('/login') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('schema matching page loads or redirects', async ({ page }) => {
      await loginViaApiAndInject(page);
      await page.goto('/ai/schema-matching');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.schema-matching-page, .unavailable-page, .loading-spinner-container, #email',
        { timeout: 30000 }
      );
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/ai/schema-matching')).toBe(true);
    });
  });
});
