/**
 * Phase 278.V.2 — Cross-tab tenant sync banner E2E.
 *
 * Validates that TenantSyncBanner (278.C.2) renders when a tenant
 * switch occurs in another browser tab via the `storage` event on
 * the `auth:tenant-switch` localStorage key.
 *
 * Multi-tab pattern: uses `context.newPage()` to simulate two tabs
 * sharing the same browser context (same localStorage). Mirrors the
 * pattern from `cross-tab-token-sync.spec.ts` (Phase 277.B.067).
 *
 * @critical — a missing banner means users continue operating on a
 * stale tenant after a cross-tab switch, which is a data-integrity
 * risk (writes go to the wrong tenant).
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

const STORAGE_KEY = 'auth:tenant-switch';

test.describe('Tenant Sync Banner (278.V.2) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('cross-tab tenant switch triggers banner in tab A', async ({
      context,
    }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      // Both tabs authenticate
      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate — backend may be unreachable');

      // Navigate both tabs to a page that renders TenantSyncBanner (home)
      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });

      // Verify app shell loaded on both tabs
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });
      await expect(tabB.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Sanity: banner should NOT be visible before the storage event
      const bannerBefore = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(bannerBefore).not.toBeVisible({ timeout: 3000 });

      // Tab B: simulate a tenant switch by writing the localStorage key.
      // The `storage` event fires in OTHER tabs (here: tab A) of the
      // same origin, NOT in the tab that called setItem.
      await tabB.evaluate((key) => {
        localStorage.setItem(key, Date.now().toString());
      }, STORAGE_KEY);

      // Tab A: the storage event listener in TenantSyncBanner should
      // detect the change and render the banner.
      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).toBeVisible({ timeout: 5000 });

      await tabA.close();
      await tabB.close();
    });

    test('banner displays correct text and refresh action', async ({
      context,
    }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Trigger tenant switch in tab B
      await tabB.evaluate((key) => {
        localStorage.setItem(key, Date.now().toString());
      }, STORAGE_KEY);

      // Verify banner content
      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).toBeVisible({ timeout: 5000 });

      // Text content
      const textEl = banner.locator('.tenant-sync-banner__text');
      await expect(textEl).toBeVisible();
      const text = await textEl.textContent();
      expect(text?.trim()).toBe('Tenant changed in another tab.');

      // Refresh action button
      const actionBtn = banner.locator('.tenant-sync-banner__action');
      await expect(actionBtn).toBeVisible();
      const actionText = await actionBtn.textContent();
      expect(actionText?.trim()).toContain('Refresh');

      await tabA.close();
      await tabB.close();
    });

    test('banner has correct a11y attributes', async ({ context }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Trigger tenant switch
      await tabB.evaluate((key) => {
        localStorage.setItem(key, Date.now().toString());
      }, STORAGE_KEY);

      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).toBeVisible({ timeout: 5000 });

      // role="alert" for immediate screen-reader announcement
      const role = await banner.getAttribute('role');
      expect(role).toBe('alert');

      // aria-live="polite" so updates don't interrupt current SR speech
      const ariaLive = await banner.getAttribute('aria-live');
      expect(ariaLive).toBe('polite');

      await tabA.close();
      await tabB.close();
    });
  });

  test.describe('Failure / Edge', () => {
    test('banner not shown when tenant unchanged', async ({ context }) => {
      const tabA = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      test.skip(tabA.url().includes('/login'), 'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Banner must not be visible when no cross-tab switch occurred
      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).not.toBeVisible({ timeout: 3000 });

      await tabA.close();
    });

    test('banner not shown when storage event has null newValue', async ({
      context,
    }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Tab B: remove the key (StorageEvent.newValue === null).
      // TenantSyncBanner checks `e.newValue` before showing — null must
      // NOT trigger the banner (only explicit sets should).
      await tabB.evaluate((key) => {
        localStorage.removeItem(key);
      }, STORAGE_KEY);

      // Give the storage event a moment to propagate
      await tabA.waitForTimeout(1000);

      // Banner must NOT appear when the key is removed (clearing state
      // is not a tenant-switch signal)
      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).not.toBeVisible({ timeout: 3000 });

      await tabA.close();
      await tabB.close();
    });

    test('dismissing banner clears it', async ({ context }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Trigger tenant switch
      await tabB.evaluate((key) => {
        localStorage.setItem(key, Date.now().toString());
      }, STORAGE_KEY);

      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).toBeVisible({ timeout: 5000 });

      // Click dismiss
      const dismissBtn = banner.locator('.tenant-sync-banner__dismiss');
      await expect(dismissBtn).toBeVisible();
      await dismissBtn.getAttribute('aria-label').then((label) => {
        expect(label).toBe('Dismiss');
      });
      await dismissBtn.click();

      // Banner must disappear after dismiss
      await expect(banner).not.toBeVisible({ timeout: 3000 });

      await tabA.close();
      await tabB.close();
    });

    test('banner appears within 2s of cross-tab switch', async ({
      context,
    }) => {
      const tabA = await context.newPage();
      const tabB = await context.newPage();

      const user = await getTestUser();
      await loginUser(tabA, user);
      await loginUser(tabB, user);
      test.skip(tabA.url().includes('/login') || tabB.url().includes('/login'),
        'Could not authenticate');

      await tabA.goto('/', { waitUntil: 'domcontentloaded' });
      await tabB.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(tabA.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 });

      // Trigger tenant switch and measure time to banner visibility
      const triggerTime = Date.now();
      await tabB.evaluate((key) => {
        localStorage.setItem(key, Date.now().toString());
      }, STORAGE_KEY);

      const banner = tabA.locator('[data-testid="tenant-sync-banner"]');
      await expect(banner).toBeVisible({ timeout: 2000 });
      const visibleTime = Date.now();
      const latency = visibleTime - triggerTime;

      // Banner must appear within 2s per acceptance criteria
      expect(latency).toBeLessThan(2000);

      await tabA.close();
      await tabB.close();
    });
  });
});
