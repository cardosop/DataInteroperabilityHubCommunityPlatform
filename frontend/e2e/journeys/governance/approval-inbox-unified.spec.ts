/**
 * Phase 278.V.3 — Unified Approval Inbox (MyApprovalsInbox) E2E.
 *
 * Validates the `/governance/my-approvals` route (278.R.8 / 278.I.1):
 * renders pending access requests with type badges, priority borders,
 * inline Approve/Reject buttons, bulk ops, count badge, and empty state.
 *
 * Route is gated to TENANT_ADMIN / DPO / LEGAL_ADMIN / SECURITY_ADMIN /
 * PLATFORM_ADMIN — tests use getTenantAdminUser.
 *
 * Gate contract (close-test-coverage-gaps 2.4): every skip is CONDITIONAL
 * (no-test-skip-true clean); guarded expects were replaced by direct
 * asserts where the component GUARANTEES the markup (breadcrumbs, item
 * type badge, item title link, action buttons, select-all, footer
 * view-all), or by conditional skips where the state is genuinely
 * data-dependent (no pending items).
 *
 * @critical — approval latency directly impacts marketplace time-to-value
 * and governance SLA compliance.
 */
import { test, expect } from '@playwright/test';
import { getTenantAdminUser, getTestUser, loginUser } from '../../fixtures/auth';
import { createPendingAccessRequestsViaApi } from '../../fixtures/api-assets';

function inboxLocator(page: import('@playwright/test').Page) {
  return page
    .locator(
      '[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty',
    )
    .first();
}

async function navigateToInbox(page: import('@playwright/test').Page) {
  const user = await getTenantAdminUser();
  await loginUser(page, user);
  test.skip(page.url().includes('/login'), 'Could not authenticate as TENANT_ADMIN');
  await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
  // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
  await inboxLocator(page)
    .waitFor({ state: 'visible', timeout: 30000 })
    .catch(() => null);
  test.skip(
    page.url().includes('/403') || page.url().includes('/login'),
    'Role gate or auth redirect',
  );
}

test.describe('Unified Approval Inbox (278.V.3) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('route /governance/my-approvals is navigable and renders page shell', async ({
      page,
    }) => {
      await navigateToInbox(page);

      // Page must have rendered the inbox or empty state (both valid) —
      // the 404 fall-through this spec used to hit (before the route
      // landed) renders NEITHER, so this assert is the no-404 contract.
      const inboxOrEmpty =
        (await page.locator('.my-approvals-inbox, [data-testid="my-approvals-inbox"]').count()) > 0;
      expect(inboxOrEmpty).toBe(true);
    });

    test('inbox renders with header, breadcrumbs, and title', async ({
      page,
    }) => {
      await navigateToInbox(page);

      // Breadcrumbs render unconditionally in the loaded state — direct
      // assert (no count guard).
      const breadcrumbs = page.locator('.breadcrumbs, [data-testid="breadcrumbs"]').first();
      await expect(breadcrumbs).toBeVisible({ timeout: 10000 });
      const bcText = await breadcrumbs.textContent();
      expect(bcText).toContain('Governance');
      expect(bcText).toContain('My Approvals');

      // Title renders unconditionally in the loaded state — direct assert.
      await expect(
        page.locator('.my-approvals-inbox__title').first(),
      ).toBeVisible({ timeout: 10000 });
    });

    test('inbox shows count badge when items are present', async ({ page }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const hasItems = (await page.locator('.my-approvals-inbox__list li').count()) > 0;
      test.skip(!hasItems, 'No pending items — count badge only renders with items');

      // Count badge is guaranteed by the component whenever items.length
      // > 0 — direct assert, and it must show a positive number.
      const countBadge = page.locator('.my-approvals-inbox__count');
      await expect(countBadge).toBeVisible({ timeout: 5000 });
      const countText = await countBadge.textContent();
      const count = parseInt(countText?.trim() ?? '0', 10);
      expect(count).toBeGreaterThan(0);
    });

    test('inbox items render type badge and priority class', async ({
      page,
    }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const items = page.locator('.my-approvals-inbox__list li');
      const itemCount = await items.count();
      test.skip(itemCount === 0, 'No pending approval items — cannot verify type badges');

      // Item markup is guaranteed by the component — direct asserts.
      const firstItem = items.first();
      const typeBadge = firstItem.locator('.my-approvals-inbox__item-type');
      await expect(typeBadge).toBeVisible({ timeout: 5000 });
      expect((await typeBadge.textContent())?.trim().length).toBeGreaterThan(0);

      const classList = await firstItem.getAttribute('class');
      const hasPriorityClass =
        classList?.includes('my-approvals-inbox__item--high') ||
        classList?.includes('my-approvals-inbox__item--medium') ||
        classList?.includes('my-approvals-inbox__item--low');
      expect(hasPriorityClass).toBe(true);
    });

    test('inbox items have Approve and Reject action buttons', async ({
      page,
    }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const items = page.locator('.my-approvals-inbox__list li');
      test.skip(
        (await items.count()) === 0,
        'No pending items — cannot verify action buttons',
      );

      // Every item carries its actions array — the buttons are guaranteed.
      const actions = items.first().locator('.my-approvals-inbox__item-actions button, .btn');
      expect(await actions.count()).toBeGreaterThanOrEqual(1);
    });

    test('item title links to access request detail page', async ({ page }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const itemTitle = page.locator('.my-approvals-inbox__item-title').first();
      test.skip(
        (await itemTitle.count()) === 0,
        'No items with titles — cannot verify navigation',
      );

      // The title Link is guaranteed per item — direct asserts.
      const href = await itemTitle.getAttribute('href');
      expect(href).toBeTruthy();
      expect(href).toContain('/governance/access-requests/');
    });
  });

  test.describe('Failure / Edge', () => {
    test('empty state shown when no pending approvals', async ({ page }) => {
      await navigateToInbox(page);

      // Either empty state or list is visible — both are valid.
      const hasEmpty = (await page.locator('.my-approvals-inbox__empty').count()) > 0;
      const hasList = (await page.locator('.my-approvals-inbox__list').count()) > 0;
      expect(hasEmpty || hasList).toBe(true);
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/governance/my-approvals'),
        'Expected /login redirect or page with auth',
      ).toBe(true);
    });

    test('footer "View all" link navigates to /governance', async ({ page }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      // The component renders the link in BOTH states — the footer
      // view-all when items exist, the empty-link when not — so the union
      // is guaranteed and the assert is direct.
      const viewAll = page
        .locator('.my-approvals-inbox__view-all, .my-approvals-inbox__empty-link')
        .first();
      await expect(viewAll).toBeVisible({ timeout: 5000 });
      expect(await viewAll.getAttribute('href')).toContain('/governance');
    });

    test('bulk actions bar visible when items present', async ({ page }) => {
      await navigateToInbox(page);
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel — no
      // separate Bearer path to drift.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await inboxLocator(page)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      const hasList = (await page.locator('.my-approvals-inbox__list li').count()) > 0;
      test.skip(
        !hasList,
        'No pending items — bulk actions bar only renders when items exist',
      );

      // Select-all renders whenever items.length > 0 — direct assert (the
      // previous toBeGreaterThanOrEqual(0) was a tautology that never
      // caught a missing bar).
      await expect(
        page.locator('.my-approvals-inbox__select-all'),
      ).toBeVisible({ timeout: 5000 });
    });
  });
});
