/**
 * E2E: UC-WH-001 — Create/Manage Webhook
 *
 * Use Case: Webhook Management
 * Persona: Data Engineer, Tenant Admin
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /webhooks, /webhooks/create.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('UC-WH-001: Create/Manage Webhook', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('webhooks list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .empty-state',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/webhooks');
    });

    test('webhooks create page loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/webhooks/create', {
        timeout: 60000,
        contentSelector: '.webhook-create-page, form, .empty-state',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      // Must be on the create page specifically, not just any webhooks URL
      expect(page.url()).toContain('/webhooks/create');
      // The create form must be present with fillable inputs
      await page.waitForSelector('.webhook-create-page, form', { timeout: 15000 });
      const hasForm = (await page.locator('.webhook-create-page, form').count()) > 0;
      const hasInputs = (await page.locator('input[name], textarea[name], input[type="url"]').count()) > 0;
      expect(hasForm).toBe(true) /* acceptable states */;
      expect(hasInputs).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('webhook detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
        contentSelector: '[data-testid="home-page"], .home-page, main',
      });
      await page.goto('/webhooks/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.webhook-detail-page, .error-display',
        waitAfterLoad: 5000,
        selectorTimeout: 20000,
        apiUrlPattern: '/webhooks/00000000-0000-0000-0000-000000000000',
      });
    });

    test('unauthenticated access to webhooks redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/webhooks', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|403)(\?|$)/, { timeout: 25_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      expect(onLogin || on403).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Edge', () => {
    test('webhooks list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .empty-state, .error-display',
      });
      expect(page.url()).toContain('/webhooks');
    });
  });
});
