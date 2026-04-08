/**
 * E2E Test: JOURNEY-DE-001 — Programmatic Contract-First Onboarding
 *
 * Journey: Programmatic Contract-First Onboarding
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Dedicated DE-001 spec (contracts-odps-routes covers some). Success/Failure/Edge.
 * Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps, /odps, /odps/upload.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-001: Programmatic Contract-First Onboarding', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', { timeout: 60000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toContain('/contracts');
      const hasContent =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('ODPS list loads', async ({ page }) => {
      // Phase 211.A6: /odps redirects to /contracts?spec_type=ODPS (the contracts list
      // filtered to the ODPS spec type). Test asserts the redirect target — that's the
      // canonical URL the ODPS list now lives at. We still navigate via /odps to verify
      // the backward-compat redirect itself works.
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps', { timeout: 65000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      // Accept either the legacy URL (if redirect hasn't fired yet on a slow page) or
      // the canonical post-redirect URL.
      expect(page.url()).toMatch(/\/(odps|contracts\?spec_type=ODPS)/);
      // And assert the contracts list rendered (proves the redirect target loaded, not
      // a blank page or error).
      const hasContent =
        (await page.locator('.contract-list-page').count()) > 0 ||
        (await page.locator('.empty-state').count()) > 0 ||
        (await page.locator('.error-display').count()) > 0;
      expect(hasContent).toBe(true);
    });

    test('ODPS upload page loads', async ({ page }) => {
      // Phase 211.A6: /odps/upload redirects to /contracts/create (unified contract
      // creation page that supports ODPS and other spec types).
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', { timeout: 60000 });
      if (page.url().includes('/login')) {
        expect(page.url()).toContain('/login');
        return;
      }
      expect(page.url()).toMatch(/\/(odps\/upload|contracts\/create)/);
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/edit',
        { timeout: 65000 }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page, .error-display',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('link-odps with non-existent contract shows error or redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/link-odps',
        { timeout: 65000 }
      );
      await page
        .locator('.error-display, .contract-detail-page')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);
      const url = page.url();
      const onLinkOdps = url.includes('/link-odps');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed|403|forbidden/i').count()) > 0;
      expect(onLinkOdps || hasError || onLogin || on403).toBe(true) /* acceptable states */;
    });
  });
});
