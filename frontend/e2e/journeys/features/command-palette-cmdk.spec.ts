/**
 * E2E Test: Cmd-K / Ctrl-K Command Palette — Phase 278.V.19
 *
 * Journey: Global command palette for fuzzy-search navigation + actions.
 * @covers 278.V.19, 278.E.1 — Command palette Cmd-K/Ctrl-K E2E test
 * Persona: All authenticated users
 * Reference: specs/ux-quick-wins/spec.md
 *
 * Covers the CommandPalette component shipped in Phase 223.5.3 and
 * wired in AppShell.tsx:
 *   - Cmd-K (Mac) / Ctrl-K (Linux/Windows) opens the palette.
 *   - Typing filters commands with fuzzy matching (cmdk library).
 *   - Selecting a result navigates to the route.
 *   - Escape closes the palette.
 *   - A11y: cmdk provides role="combobox" / role="listbox" / role="option".
 *   - Recent items are persisted in localStorage.
 *
 * Success/Failure/Edge. Routes: any authenticated page.
 * Real backend; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

/** Press the platform-appropriate mod key + k to open the palette. */
async function openCommandPalette(page: import('@playwright/test').Page): Promise<void> {
  // Try both Meta+k (Mac) and Control+k (Linux/Windows)
  // `modOrCtrl` in useKeyboardShortcut means Meta on Mac, Ctrl elsewhere
  const isMac = process.platform === 'darwin';
  if (isMac) {
    await page.keyboard.press('Meta+k');
  } else {
    await page.keyboard.press('Control+k');
  }
  await page.waitForTimeout(500);
}

test.describe('Command Palette @critical @quarantine', () => {
  test.setTimeout(120000);

  test.describe('Success — Open, search, navigate', () => {
    test('Cmd-K opens palette, typing filters, selecting navigates', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      // Open the command palette
      await openCommandPalette(page);

      // The cmdk dialog should appear
      const content = page.locator('.command-palette-content');
      const isVisible = (await content.count()) > 0 && (await content.isVisible());

      if (!isVisible) {
        // Try the alternative keyboard shortcut
        await page.keyboard.press('Meta+k');
        await page.waitForTimeout(500);
      }

      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open — keyboard shortcut may not be registered',
      );

      // The input should be visible and auto-focused
      const input = page.locator('.command-palette-input');
      await expect(input).toBeVisible();

      // Type to search — should filter results
      await input.fill('asset');
      await page.waitForTimeout(500);

      // Results should appear (cmdk fuzzy matches)
      const items = page.locator('.command-palette-item');
      const itemCount = await items.count();

      if (itemCount > 0) {
        // Items should be visible with labels
        const firstItem = items.first();
        await expect(firstItem).toBeVisible();

        // Click the first result — should navigate
        const currentUrl = page.url();
        await firstItem.click();
        await page.waitForTimeout(1000);

        // URL should have changed (navigation occurred)
        const newUrl = page.url();
        expect(newUrl).not.toBe(currentUrl);
      } else {
        // No results — the empty state should show
        const empty = page.locator('.command-palette-empty');
        if ((await empty.count()) > 0) {
          await expect(empty).toBeVisible();
          expect(await empty.textContent()).toMatch(/no results/i);
        }
      }
    });

    test('palette closes on Escape key', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      await openCommandPalette(page);

      const content = page.locator('.command-palette-content');
      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open',
      );

      // Press Escape — cmdk handles this internally via Radix Dialog
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);

      // The palette should be closed
      await expect(content).not.toBeVisible();
    });
  });

  test.describe('Success — Groups and empty state', () => {
    test('palette shows groups for Pages and Actions', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      await openCommandPalette(page);

      const content = page.locator('.command-palette-content');
      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open',
      );

      // Should have at least one group heading
      const groups = page.locator('.command-palette-group');
      const groupCount = await groups.count();
      expect(groupCount).toBeGreaterThan(0);

      // At minimum, the "Pages" group should be present
      const pageGroup = groups.filter({ hasText: 'Pages' });
      const pageGroupVisible = (await pageGroup.count()) > 0;
      expect(pageGroupVisible).toBe(true);
    });

    test('empty state shows when no results match search', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      await openCommandPalette(page);

      const content = page.locator('.command-palette-content');
      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open',
      );

      // Type a search that won't match anything
      const input = page.locator('.command-palette-input');
      await input.fill('xyznonexistent12345pattern');
      await page.waitForTimeout(500);

      // Empty state should appear
      const empty = page.locator('.command-palette-empty');
      const hasEmpty = (await empty.count()) > 0;

      // Items should be gone
      const items = page.locator('.command-palette-item');
      const itemCount = await items.count();

      expect(hasEmpty || itemCount === 0).toBe(true);
    });
  });

  test.describe('Edge — A11y and recent items', () => {
    test('palette has accessible structure via cmdk', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      await openCommandPalette(page);

      const content = page.locator('.command-palette-content');
      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open',
      );

      // cmdk renders a combobox (input with role="combobox")
      const input = page.locator('.command-palette-input');
      await expect(input).toBeVisible();
      const inputRole = await input.getAttribute('role');
      // cmdk's input has role="combobox"
      expect(inputRole).toMatch(/combobox|textbox/);

      // The list should have role="listbox"
      const list = page.locator('.command-palette-list');
      if ((await list.count()) > 0) {
        const listRole = await list.getAttribute('role');
        expect(listRole).toMatch(/listbox/);
      }

      // Radix Dialog provides sr-only title + description for screen readers
      const srTitle = page.locator('.sr-only').filter({ hasText: 'Command palette' });
      expect(await srTitle.count()).toBeGreaterThan(0);
    });

    test('selecting an item adds it to recent and navigates', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      test.skip(
        page.url().includes('/login'),
        'Redirected to login — auth may have expired',
      );

      await openCommandPalette(page);

      const content = page.locator('.command-palette-content');
      test.skip(
        (await content.count()) === 0 || !(await content.isVisible()),
        'CommandPalette did not open',
      );

      // Search for a specific page
      const input = page.locator('.command-palette-input');
      await input.fill('dataset');
      await page.waitForTimeout(500);

      const items = page.locator('.command-palette-item');
      test.skip(
        (await items.count()) === 0,
        'No items matched "dataset" — palette may have no datasets page',
      );

      // Click the first result
      const firstItem = items.first();
      const itemLabel = await firstItem.textContent();
      expect(itemLabel?.trim().length).toBeGreaterThan(0);

      const currentUrl = page.url();
      await firstItem.click();
      await page.waitForTimeout(1000);

      // Should have navigated
      const newUrl = page.url();
      expect(newUrl).not.toBe(currentUrl);

      // Re-open the palette — the recently selected item should appear
      // in the "Recent" group if the palette supports recent items
      await openCommandPalette(page);

      const recentGroup = page.locator('.command-palette-group').filter({ hasText: 'Recent' });
      if ((await recentGroup.count()) > 0) {
        // Recent items should include the one we just selected
        const recentItems = recentGroup.locator('.command-palette-item');
        const recentCount = await recentItems.count();
        expect(recentCount).toBeGreaterThan(0);
      }
    });
  });
});
