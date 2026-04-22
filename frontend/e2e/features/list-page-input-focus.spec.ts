/**
 * E2E Feature: Track B — text-input cursor-loss regression guard.
 *
 * Verifies that list-page search/filter inputs retain focus across keystrokes
 * when the query key changes and a refetch fires. Protects against the bug
 * fixed by:
 *   (1) global `placeholderData: keepPreviousData` in AppProviders (so
 *       isLoading does not flip to true on key change, and the
 *       `if (isLoading) return <Skeleton />` early-return doesn't unmount
 *       the input), AND
 *   (2) structural inversion on every list page (filter bar renders above
 *       the isLoading guard as defense-in-depth).
 *
 * Real backend only; no mocks. Uses `toBeFocused()` auto-wait instead of
 * polling `document.activeElement` to avoid flakiness on CI.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Feature: Track B — list-page input focus retention', () => {
  test.setTimeout(120000);

  type PageCase = {
    name: string;
    url: string;
    /** Input locator — prefer id to role='searchbox' since not every input uses role. */
    inputLocator: string;
    /** Selector shown once the page has committed to rendering (any of comma-separated list). */
    contentSelector: string;
  };

  const PAGES: PageCase[] = [
    {
      name: '/assets search input',
      url: '/assets',
      inputLocator: '#asset-search',
      contentSelector: '.asset-list-page, .empty-state',
    },
    {
      name: '/datasets asset-id filter input',
      url: '/datasets',
      inputLocator: '#dataset-asset-id-filter',
      contentSelector: '.dataset-list-page, .empty-state',
    },
    {
      name: '/governance/retention asset-id filter input',
      url: '/governance/retention',
      inputLocator: '#asset-id-filter',
      contentSelector: '.governance-retention-policy-list-page, .empty-state',
    },
    {
      name: '/audit actor-user-id filter input',
      url: '/audit',
      inputLocator: '#audit-actor-filter',
      contentSelector: '.audit-event-list-page, .empty-state',
    },
  ];

  for (const pageCase of PAGES) {
    test(`input retains focus while typing on ${pageCase.name}`, async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, pageCase.url, {
        timeout: 60000,
        contentSelector: pageCase.contentSelector,
      });

      const input = page.locator(pageCase.inputLocator);
      // Input must be rendered regardless of list state (loading/error/empty/success).
      await expect(input).toBeVisible({ timeout: 30000 });
      await input.focus();
      await expect(input).toBeFocused();

      // Type multiple characters with a short delay. Even if each keystroke
      // triggers a React Query key change, keepPreviousData keeps isLoading
      // false, so the search input DOM node is never unmounted.
      await input.fill('');
      await input.type('abcde', { delay: 40 });

      // The canonical Track B regression would cause focus loss after one or
      // more keystrokes. These two auto-waiting assertions catch it:
      await expect(input).toHaveValue('abcde');
      await expect(input).toBeFocused();
    });
  }
});
