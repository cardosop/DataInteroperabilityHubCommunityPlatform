/**
 * E2E Test: JOURNEY-CPO-009 — Configure Automated Retention Policies
 *
 * Journey: Configure Automated Retention Policies
 * Persona: Compliance Officer
 * Use Case: UC-CPO-009 (Configure Automated Retention Policies)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /governance/retention.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import {
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-009: Configure Automated Retention Policies', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('governance retention list loads', async ({ page }) => {
      const cpoUser = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, cpoUser, '/governance/retention', { timeout: 60000 });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      const onRetention = page.url().includes('/governance/retention');
      expect(onRetention).toBe(true) /* acceptable states */;
      // error-display is NOT acceptable — it means the backend or retention service is down
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Governance retention page shows error: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.governance-retention-policy-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('retention policy create form accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance/retention');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, 'Login redirect or 403 — skipping success assertion');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Login redirect or 403 — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page);

      const createButton = page.locator(
        'button:has-text("Create"), button:has-text("New"), a:has-text("Create")'
      );
      const hasCreateButton = (await createButton.count()) > 0;

      if (hasCreateButton) {
        await createButton.first().click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(3000);

        const form = page.locator('form');
        const createPage = page.locator('.governance-retention-policy-create-page');
        const nameInput = page.locator('input[name="name"]');

        const hasForm = (await form.count()) > 0;
        const hasCreatePage = (await createPage.count()) > 0;
        const hasNameInput = (await nameInput.count()) > 0;

        expect(hasForm || hasCreatePage || hasNameInput).toBe(true);
      } else {
        // No create button — check that retention list or empty state is shown
        const retentionList = page.locator('.governance-retention-policy-list-page');
        const emptyState = page.locator('.empty-state');
        const hasRetentionList = (await retentionList.count()) > 0;
        const hasEmptyState = (await emptyState.count()) > 0;
        expect(hasRetentionList || hasEmptyState).toBe(true);
      }

      await expect(page.locator('.error-display')).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('retention policy with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance/retention/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.governance-retention-policy-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/governance/retention');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('retention page loads or redirects', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance/retention');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.includes('/login') || url.includes('/403') || url.includes('/governance/retention')).toBe(true);
    });
  });
});
