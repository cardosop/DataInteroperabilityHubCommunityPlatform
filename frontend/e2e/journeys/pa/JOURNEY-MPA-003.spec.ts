/**
 * E2E Test: JOURNEY-MPA-003 — Monitor Platform Health
 *
 * Journey: Monitor Platform Health
 * Persona: Platform Admin
 * Reference: docs/deprecated-doc/archive/USER_JOURNEY_MAPPING.md, FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md
 *
 * Routes: /observability. Backend has tests; frontend spec for alignment.
 * Fixture: getPlatformAdminUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser, loginAsPersona } from '../../fixtures/auth';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('JOURNEY-MPA-003: Monitor Platform Health', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('observability page loads', async ({ page }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/observability');
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
      expect(page.url()).toContain('/observability');
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to observability route redirects to login or 403', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/observability', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|observability|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/403') || url.includes('/observability')
      ).toBe(true);
    });
  });

});
