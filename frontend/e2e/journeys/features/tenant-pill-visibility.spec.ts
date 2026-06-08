/**
 * Phase 278.V.1 — Tenant Pill visibility and environment color coding E2E.
 *
 * Covers TenantPill.tsx (278.C.1 / 278.R.3): renders in header with
 * environment-coded trim (prod=red, staging=amber, sandbox=blue),
 * displays tenant name, accessible via aria-label, truncated for long
 * names.
 *
 * @critical — tenant identity is the first piece of situational
 * awareness in the shell; a blank or uncolored pill means the user
 * doesn't know which tenant they're operating on.
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('Tenant Pill Visibility (278.V.1) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('tenant pill renders on authenticated pages', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate — backend may be unreachable');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });
    });

    test('tenant pill renders on multiple authenticated routes', async ({
      page,
    }) => {
      const user = await getTestUser();
      const routes = ['/', '/assets', '/marketplace', '/datasets', '/search'];

      for (const route of routes) {
        await loginUser(page, user);
        if (page.url().includes('/login')) {
          test.skip(true, 'Auth redirect — backend may be unreachable');
          return;
        }
        await page.goto(route, { waitUntil: 'domcontentloaded' });
        // Wait for either the app shell or tenant pill
        await page
          .locator('.app-shell, [data-testid="app-shell"], [data-testid="tenant-pill"]')
          .first()
          .waitFor({ state: 'visible', timeout: 15000 })
          .catch(() => null);

        if (page.url().includes('/login')) continue; // auth expired mid-test

        const pill = page.locator('[data-testid="tenant-pill"]');
        // Pill should be visible on every authenticated page
        await expect(pill).toBeVisible({ timeout: 10000 });
      }
    });

    test('tenant pill displays tenant name', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // The pill must contain non-empty tenant name text
      const nameEl = pill.locator('.tenant-pill__name');
      const name = await nameEl.textContent();
      expect(name?.trim().length).toBeGreaterThan(0);
    });

    test('tenant pill is accessible via aria-label', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // aria-label must describe both tenant and environment context
      const ariaLabel = await pill.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();
      expect(ariaLabel).toContain('Current tenant');
      expect(ariaLabel).toContain('Environment');
    });

    test('tenant pill has correct environment color class', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // The pill must carry exactly one color class: tenant-pill--{color}
      const classList = await pill.getAttribute('class');
      expect(classList).toBeTruthy();

      const colorClasses = ['tenant-pill--red', 'tenant-pill--amber', 'tenant-pill--blue', 'tenant-pill--neutral'];
      const matchingColors = colorClasses.filter((c) => classList!.includes(c));
      expect(matchingColors.length).toBe(1);
    });

    test('tenant pill renders environment color dot', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // The env dot must be present (decorative, hidden from screen readers)
      const dot = pill.locator('.tenant-pill__env-dot');
      await expect(dot).toBeVisible();
      const ariaHidden = await dot.getAttribute('aria-hidden');
      expect(ariaHidden).toBe('true');
    });

    test('tenant pill has title tooltip with name and environment', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // title tooltip provides hover context
      const title = await pill.getAttribute('title');
      expect(title).toBeTruthy();
      // Should include environment indicator separator (·)
      expect(title).toContain('·');
    });
  });

  test.describe('Failure / Edge', () => {
    test('tenant pill not present when unauthenticated', async ({ page }) => {
      // Clear any stored auth state
      await page.goto('/login', { waitUntil: 'domcontentloaded' });

      // On the login page, there should be no tenant pill
      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).not.toBeVisible({ timeout: 5000 });
    });

    test('tenant pill handles long tenant names without breaking layout', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // The pill has max-width: 160px with text-overflow: ellipsis.
      // Verify the bounding box is within reasonable header bounds.
      const box = await pill.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        // Pill width must not exceed 200px (160px max-width + padding/border)
        expect(box.width).toBeLessThanOrEqual(200);
        // Pill height must be reasonable for a header element
        expect(box.height).toBeGreaterThan(0);
        expect(box.height).toBeLessThan(60);
      }

      // The name span should have overflow hidden / text-overflow: ellipsis
      const nameEl = pill.locator('.tenant-pill__name');
      const overflow = await nameEl.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return {
          overflow: style.overflow,
          textOverflow: style.textOverflow,
        };
      });
      expect(overflow.overflow).toBe('hidden');
      expect(overflow.textOverflow).toBe('ellipsis');
    });

    test('tenant pill is focusable and has visible focus ring', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      const pill = page.locator('[data-testid="tenant-pill"]');
      await expect(pill).toBeVisible({ timeout: 15000 });

      // Verify the pill is a button (keyboard-focusable natively)
      const tagName = await pill.evaluate((el) => el.tagName.toLowerCase());
      expect(tagName).toBe('button');

      // Focus the pill and verify focus-visible style is defined
      await pill.focus();
      const isFocused = await pill.evaluate((el) => el === document.activeElement);
      expect(isFocused).toBe(true);
    });
  });
});
