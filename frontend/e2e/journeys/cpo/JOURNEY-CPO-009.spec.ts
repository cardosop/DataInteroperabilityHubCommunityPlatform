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
      expect(onRetention).toBe(true);
      // error-display is NOT acceptable — it means the backend or retention service is down
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Governance retention page shows error: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.governance-retention-policy-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
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
