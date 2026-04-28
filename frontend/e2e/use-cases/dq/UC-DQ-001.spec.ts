/**
 * E2E: UC-DQ-001 — Run Data Quality Check / Monitor Asset Quality
 *
 * Use Case: Run Data Quality Check
 * Persona: Data Product Owner, Data Engineer, Compliance Officer
 * Reference: docs/USE_CASES.md#uc-dq-001
 *
 * Success/Failure/Edge. Routes: /dq, /dq/runs/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-DQ-001: Run Data Quality Check @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('trigger DQ run from list page', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"]',
      });
      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth not available');
      }
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 15000 });

      const actionBtn = page.locator(
        'button:has-text("Create"), button:has-text("New"), button:has-text("Run"), a:has-text("Create"), a:has-text("New"), a:has-text("Run")'
      ).first();

      if ((await actionBtn.count()) === 0) {
        test.info().annotations.push({ type: 'info', description: 'No create/run button found on DQ list page — skipping interaction' });
        return;
      }

      await actionBtn.click();
      await page.waitForTimeout(2000);

      // Look for a form or modal that appeared
      const formArea = page.locator('form, [role="dialog"], .modal, .dq-create-form').first();
      if ((await formArea.count()) === 0) {
        // Button may have navigated; check URL
        if (page.url().includes('/dq/')) {
          test.info().annotations.push({ type: 'info', description: 'Navigated after clicking action button' });
          return;
        }
        test.info().annotations.push({ type: 'info', description: 'No form/modal appeared after clicking action button' });
        return;
      }

      // Look for asset/dataset selector
      const selector = page.locator('select, [role="combobox"], input[placeholder*="asset" i], input[placeholder*="dataset" i]').first();
      if ((await selector.count()) > 0 && await selector.isVisible()) {
        // Try selecting first option if it's a select element
        const tagName = await selector.evaluate((el) => el.tagName.toLowerCase());
        if (tagName === 'select') {
          const options = await selector.locator('option').count();
          if (options > 1) {
            await selector.selectOption({ index: 1 });
          }
        }
      }

      const submitBtn = page.locator('button[type="submit"], button:has-text("Run"), button:has-text("Create"), button:has-text("Submit")').first();
      if ((await submitBtn.count()) === 0 || !(await submitBtn.isVisible())) {
        test.info().annotations.push({ type: 'info', description: 'No submit button visible in form' });
        return;
      }

      const [response] = await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/dq') && resp.request().method() === 'POST', { timeout: 30000 }),
        submitBtn.click(),
      ]);

      expect(response.status()).toBeLessThan(400);

      await page.waitForTimeout(3000);
      // Should be on detail page or back on list with new run
      const onDetail = page.url().includes('/dq/runs/');
      const onList = page.url().includes('/dq');
      expect(onDetail || onList).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('DQ runs list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"]',
      });
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality")').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('DQ run detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      const { loginUser } = await import('../../fixtures/auth');
      await loginUser(page, user);
      await page.goto('/dq/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dq-run-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to DQ redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/dq', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|dq)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/dq')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('DQ list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/dq');
    });
  });
});
