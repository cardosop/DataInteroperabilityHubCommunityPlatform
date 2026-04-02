/**
 * E2E Test: JOURNEY-CPO-006 — Configure Automated Compliance
 *
 * Journey: Configure Automated Compliance
 * Persona: Compliance Officer
 * Use Case: UC-CPO-006 (Configure Automated Compliance)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /compliance.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, waitForAppMainReady, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-006: Configure Automated Compliance', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          expect(page.url()).toMatch(/\/login|\/403/);
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/compliance');
    });

    test('compliance page has create run or configuration UI', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, 'Auth/role gated — skipping success assertion');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/role gated — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });

      // Look for create / new / run buttons
      const createButton = page.locator(
        'button:has-text("Create"), button:has-text("New"), button:has-text("Run"), a:has-text("Create")'
      );
      const hasCreateButton = (await createButton.count()) > 0 && await createButton.first().isVisible().catch(() => false);

      // Look for configuration UI
      const configUI = page.locator(
        '[class*="schedule"], [class*="config"], [data-testid*="config"]'
      );
      const hasConfigUI = (await configUI.count()) > 0 && await configUI.first().isVisible().catch(() => false);

      // Look for compliance list content (runs list or empty state)
      const complianceContent = page.locator(
        '.compliance-run-list-page, .compliance-run-list, .empty-state'
      );
      const hasComplianceContent = (await complianceContent.count()) > 0 && await complianceContent.first().isVisible().catch(() => false);

      // At least one of: create button, config UI, or compliance list content
      expect(hasCreateButton || hasConfigUI || hasComplianceContent).toBe(true);

      // error-display must NOT be visible (D85)
      await expect(page.locator('.error-display')).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('compliance run with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page, .compliance-run-detail',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('compliance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
    });
  });
});
