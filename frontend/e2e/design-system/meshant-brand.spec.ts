/**
 * E2E: Meshant Brand Display (Phase 29.0.1)
 * Verifies Header, LandingPage, LoginPage display APP_NAME; document title is correct.
 * Uses shared constant (E2E_APP_NAME) — no hardcoded "Meshant" in spec.
 */
import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../fixtures/auth';
import { E2E_APP_NAME } from '../fixtures/brand';

test.describe('Meshant Brand Display (Phase 29.0)', () => {
  test('Header displays APP_NAME', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const header = page.locator('.app-header, [data-testid="app-header"]').first();
    await expect(header).toBeVisible({ timeout: 15000 });
    await expect(header.locator('.app-title')).toContainText(E2E_APP_NAME);
  });

  test('LandingPage h1 displays APP_NAME', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);

    const h1 = page.locator('.landing-hero-title, .landing-page h1, h1').first();
    await expect(h1).toBeVisible({ timeout: 10000 });
    await expect(h1).toContainText(E2E_APP_NAME);
  });

  test('LoginPage h1 displays APP_NAME', async ({ page }) => {
    await clearAuthStorage(page);
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const h1 = page.locator('h1');
    await expect(h1).toBeVisible({ timeout: 10000 });
    await expect(h1).toContainText(E2E_APP_NAME);
  });

  test('document title is APP_NAME', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    await expect(page).toHaveTitle(E2E_APP_NAME);
  });
});
