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
import {
  getAuditorUser,
  getTenantAdminUser,
  getTestUser,
  type TestUser,
} from '../fixtures/auth';
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
    /**
     * Persona for role-gated routes. The default e2e user is
     * DATA_PROVIDER-only; /governance/* requires TENANT_ADMIN/DPO/… and
     * /audit requires TENANT_ADMIN/AUDITOR/…, so the default user bounced
     * to /403 and the filter input never rendered (b7 #34/#35: 30s
     * "element not found" hiding the role redirect).
     */
    userGetter?: () => Promise<TestUser>;
  };

  const PAGES: PageCase[] = [
    {
      name: '/assets search input',
      url: '/assets',
      inputLocator: '#asset-search',
      contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"]',
    },
    {
      name: '/datasets asset-id filter input',
      url: '/datasets',
      inputLocator: '#dataset-asset-id-filter',
      contentSelector: '.dataset-list-page, [data-testid="dataset-list-page"], .empty-state, [data-testid="empty-state"]',
    },
    {
      name: '/governance/retention asset-id filter input',
      url: '/governance/retention',
      inputLocator: '#asset-id-filter',
      contentSelector: '.governance-retention-policy-list-page, .empty-state, [data-testid="empty-state"]',
      userGetter: getTenantAdminUser,
    },
    {
      name: '/audit actor-user-id filter input',
      url: '/audit',
      inputLocator: '#audit-actor-filter',
      contentSelector: '.audit-event-list-page, [data-testid="audit-event-list-page"], .empty-state, [data-testid="empty-state"]',
      userGetter: getAuditorUser,
    },
  ];

  for (const pageCase of PAGES) {
    test(`input retains focus while typing on ${pageCase.name}`, async ({ page }) => {
      const testUser = pageCase.userGetter ? await pageCase.userGetter() : await getTestUser();
      await loginAndNavigateToRoute(page, testUser, pageCase.url, {
        timeout: 60000,
        contentSelector: pageCase.contentSelector,
      });

      // A /403 here means the route's ProtectedRoute guard bounced the
      // persona that was supposed to pass it (role-seeding drift) — the
      // Track B input contract cannot run and a 30s "element not found"
      // would mask the real signal. Fail fast with the actual URL.
      if (page.url().includes('/403')) {
        throw new Error(
          `list-page-input-focus: ${pageCase.name} redirected to /403 — ` +
            'the persona for this route lacks its ProtectedRoute role (ensure_e2e_user_roles drift?)'
        );
      }

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
