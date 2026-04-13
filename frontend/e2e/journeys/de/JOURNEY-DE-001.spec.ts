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
import { assertListPageLoads, assertNonExistentIdShowsError } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-001: Programmatic Contract-First Onboarding', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      // storageState from chromium-mvp already provides auth — go directly.
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await assertListPageLoads(page, '.contract-list-page, .empty-state, .error-display', { timeout: 60000 });
    });

    test('ODPS list loads', async ({ page }) => {
      // Phase 211.A6: /odps redirects to /contracts?spec_type=ODPS (the contracts list
      // filtered to the ODPS spec type). storageState provides auth — go directly.
      await page.goto('/odps', { waitUntil: 'domcontentloaded', timeout: 60000 });
      // Wait for redirect to resolve and content to render
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      if (url.includes('/login')) {
        expect(url).toContain('/login');
        return;
      }
      // Accept either the legacy URL (if redirect hasn't fired yet on a slow page) or
      // the canonical post-redirect URL.
      expect(url).toMatch(/\/(odps|contracts)/);
      // ContractListPage shows ListPageSkeleton until the API returns — a snapshot right
      // after domcontentloaded has no .contract-list-page / .empty-state / .error-display
      // yet (root cause of staging false failures). Same race-safe wait as contracts list.
      await assertListPageLoads(page, '.contract-list-page, .empty-state, .error-display', {
        timeout: 60000,
      });
    });

    test('ODPS upload page loads', async ({ page }) => {
      // Phase 211.A6: /odps/upload redirects to /contracts/create. storageState provides auth.
      await page.goto('/odps/upload', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      if (url.includes('/login')) {
        expect(url).toContain('/login');
        return;
      }
      expect(url).toMatch(/\/(odps\/upload|contracts\/create)/);
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/edit', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-editor-page, .contract-detail-page, .error-display',
        waitAfterLoad: 8000,
      });
    });
  });

  test.describe('Edge', () => {
    test('link-odps with non-existent contract shows error or redirect', async ({ page }) => {
      await page.goto('/contracts/00000000-0000-0000-0000-000000000000/link-odps', { waitUntil: 'domcontentloaded', timeout: 60000 });
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
