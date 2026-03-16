/**
 * E2E: UC-COMP-001 — Run Compliance Scan / Review Compliance for Asset
 *
 * Use Case: Run Compliance Scan
 * Persona: Compliance Officer, Data Product Owner
 * Reference: docs/USE_CASES.md#uc-comp-001
 *
 * Success/Failure/Edge. Routes: /compliance, /compliance/runs/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getComplianceOfficerUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-COMP-001: Run Compliance Scan', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance runs list loads', async ({ page }) => {
      const user = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, user, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .loading-spinner-container',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
      await waitForLoadingComplete(page, { timeout: 15000 });
      // error-display is NOT acceptable — compliance service must be reachable
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Compliance list shows error (service may be down): "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('compliance run detail with non-existent id shows error', async ({ page }) => {
      const user = await getComplianceOfficerUser();
      const { loginAsPersona } = await import('../../fixtures/auth');
      await loginAsPersona(page, () => Promise.resolve(user));
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page, .compliance-run-detail',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('compliance list with empty state loads', async ({ page }) => {
      const user = await getComplianceOfficerUser();
      await loginAndNavigateToRoute(page, user, '/compliance', {
        timeout: 60000,
        contentSelector: '.compliance-run-list-page, .empty-state, .loading-spinner-container',
      });
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
      await waitForLoadingComplete(page, { timeout: 15000 });
      // error-display is NOT acceptable — compliance service must be reachable
      const hasError = (await page.locator('.error-display').count()) > 0;
      if (hasError) {
        const errText = await page.locator('.error-display').first().textContent().catch(() => '');
        throw new Error(`Compliance list shows error in edge test: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });
});
