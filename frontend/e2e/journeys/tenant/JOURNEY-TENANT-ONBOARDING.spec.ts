/**
 * E2E Test: Phase 16 — Self-Service Organization Tenant Onboarding
 *
 * Visitor can create an organization (non-personal tenant) with first user as admin.
 * Route: /onboard-org
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Phase 16: Self-Service Organization Onboarding', () => {
  test.setTimeout(120000);

  test('onboard-org page loads and shows form', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/onboard-org');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('[data-testid="org-onboarding-page"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h1:has-text("Create organization")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="org-onboarding-name"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="org-onboarding-email"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="org-onboarding-password"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="org-onboarding-submit"]')).toBeVisible({ timeout: 5000 });
  });

  test('visitor can create organization and redirects to login', async ({ page }) => {
    await clearAuthStorage(page);
    const unique = `org-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const email = `onboard-${unique}@example.com`;
    const slug = `tenant-${unique}`.replace(/[^a-z0-9-]/g, '-');

    await page.goto('/onboard-org');
    await page.waitForLoadState('domcontentloaded');
    await waitForLoadingComplete(page, { timeout: 15000 });

    await page.fill('[data-testid="org-onboarding-name"]', `Test Org ${unique}`);
    await page.fill('[data-testid="org-onboarding-slug"]', slug);
    await page.fill('[data-testid="org-onboarding-email"]', email);
    await page.fill('[data-testid="org-onboarding-password"]', 'SecurePass123!');

    await page.click('[data-testid="org-onboarding-submit"]');
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test('landing page has Create organization link', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    const onboardLink = page.locator('[data-testid="landing-onboard-org-link"]');
    await expect(onboardLink).toBeVisible({ timeout: 5000 });
    expect(await onboardLink.getAttribute('href')).toContain('/onboard-org');
  });
});
