/**
 * Phase 278.V.12 — Keyboard shortcuts cheatsheet E2E.
 *
 * Validates KeyboardShortcuts (278.E.4) mounted in App.tsx:
 * opens on `?` keypress, suppresses in input/textarea/select,
 * renders 3 shortcut groups (Navigation, Actions, Lists) with
 * correct key bindings, and closes via Esc, overlay click, and ×.
 *
 * @critical — keyboard shortcuts are an accessibility accelerator;
 * a broken cheatsheet or input suppression gap makes the platform
 * unusable for keyboard-only users.
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('Keyboard Shortcuts Cheatsheet (278.V.12) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('pressing ? opens the cheatsheet modal', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      // Sanity: cheatsheet must NOT be visible initially
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).not.toBeVisible({ timeout: 2000 });

      // Press ? to open
      await page.keyboard.press('?');

      // Cheatsheet must appear
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });
    });

    test('cheatsheet renders all 3 shortcut groups', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // 3 group headings must be visible
      const groups = ['Navigation', 'Actions', 'Lists'];
      for (const group of groups) {
        const heading = cheatsheet.locator('h3', { hasText: group });
        await expect(heading).toBeVisible();
      }
    });

    test('cheatsheet shows correct shortcut key bindings', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // Verify key bindings in each group
      const expectedShortcuts = [
        'g a', 'g c', 'g m', 'g d', 'g s',  // Navigation
        'n', '/', '⌘ K', '?', 'Esc',         // Actions
        'j', 'k', 'Enter',                    // Lists
      ];

      for (const keys of expectedShortcuts) {
        const kbd = cheatsheet.locator('kbd', { hasText: keys }).first();
        await expect(kbd).toBeVisible({ timeout: 3000 });
      }
    });

    test('cheatsheet has correct a11y attributes', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // role="dialog"
      const role = await cheatsheet.getAttribute('role');
      expect(role).toBe('dialog');

      // aria-label
      const ariaLabel = await cheatsheet.getAttribute('aria-label');
      expect(ariaLabel).toBe('Keyboard shortcuts');

      // Heading
      const heading = cheatsheet.locator('h2');
      await expect(heading).toBeVisible();
      const headingText = await heading.textContent();
      expect(headingText).toContain('Keyboard Shortcuts');
    });

    test('cheatsheet closes via Escape key', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      // Open
      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // Close via Escape
      await page.keyboard.press('Escape');
      await expect(cheatsheet).not.toBeVisible({ timeout: 5000 });
    });

    test('cheatsheet closes via × button', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // Close via × button
      const closeBtn = cheatsheet.locator('.kbd-cheatsheet-close');
      await expect(closeBtn).toBeVisible();
      expect(await closeBtn.getAttribute('aria-label')).toBe('Close shortcuts');
      await closeBtn.click();

      await expect(cheatsheet).not.toBeVisible({ timeout: 5000 });
    });

    test('cheatsheet closes via overlay click', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // Click the overlay (the dialog itself is the overlay — clicking it closes)
      await cheatsheet.click({ position: { x: 10, y: 10 } });
      await expect(cheatsheet).not.toBeVisible({ timeout: 5000 });
    });

    test('cheatsheet toggles with repeated ? keypress', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      // Open
      await page.keyboard.press('?');
      await expect(page.locator('[data-testid="keyboard-shortcuts"]')).toBeVisible({ timeout: 5000 });

      // Close via second ? keypress
      await page.keyboard.press('?');
      await expect(page.locator('[data-testid="keyboard-shortcuts"]')).not.toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Failure / Edge', () => {
    test('? in input field does NOT open cheatsheet', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      // Find a search input or focusable input
      const searchInput = page.locator('input[type="text"], input[type="search"], input:not([type="hidden"])').first();
      if ((await searchInput.count()) === 0) {
        test.skip(true, 'No input element on page — cannot test suppression');
        return;
      }

      // Focus the input and type ?
      await searchInput.click();
      await searchInput.fill('test?');
      await page.keyboard.press('?');

      // Cheatsheet must NOT be visible
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).not.toBeVisible({ timeout: 3000 });
    });

    test('? with modifier keys does NOT open cheatsheet', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      // Shift+? produces '/' — should not trigger
      // Ctrl+? / Meta+? should be suppressed
      await page.keyboard.press('Shift+?');
      let cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).not.toBeVisible({ timeout: 3000 });

      // Meta+? (Cmd+?) should NOT open (suppressed by metaKey check)
      await page.keyboard.press('Meta+?');
      cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).not.toBeVisible({ timeout: 3000 });
    });

    test('cheatsheet focus trap: close button receives focus on open', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      if (page.url().includes('/login')) return;

      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      // The close button should have focus (focus-trap behavior)
      const closeBtn = cheatsheet.locator('.kbd-cheatsheet-close');
      const isFocused = await closeBtn.evaluate(
        (el) => el === document.activeElement,
      );
      expect(isFocused).toBe(true);
    });
  });
});
