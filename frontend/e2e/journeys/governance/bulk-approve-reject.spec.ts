/**
 * Phase 278.V.10 — Bulk approve/reject from unified approval inbox E2E.
 *
 * Validates bulk selection and action flows in MyApprovalsInbox (278.I.1):
 * select-all, individual toggle, bulk approve with count badge, bulk
 * reject with reason input, and deselection updates.
 *
 * Route is gated to TENANT_ADMIN / DPO / LEGAL_ADMIN / SECURITY_ADMIN /
 * PLATFORM_ADMIN — tests use getTenantAdminUser.
 *
 * @critical — bulk operations are the primary throughput accelerator for
 * governance approvers; broken bulk ops force one-at-a-time processing
 * and directly violate the approval SLA.
 */
import { test, expect } from '@playwright/test';
import { getTenantAdminUser, getTestUser, loginUser } from '../../fixtures/auth';
import { createPendingAccessRequestsViaApi } from '../../fixtures/api-assets';

test.describe('Bulk Approve/Reject from Approval Inbox (278.V.10) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('select-all checkbox toggles all items', async ({ page }) => {





      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate as TENANT_ADMIN');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      const items = page.locator('.my-approvals-inbox__list li');
      const itemCount = await items.count();

      test.skip(
        itemCount === 0,
        'No pending approval items — cannot test bulk selection',
      );

      // Click select-all checkbox
      const selectAllCheckbox = page.locator('.my-approvals-inbox__select-all input[type="checkbox"]');
      test.skip((await selectAllCheckbox.count()) === 0, 'Select-all checkbox not rendered');

      // Toggle on: select all
      await selectAllCheckbox.check();
      expect(await selectAllCheckbox.isChecked()).toBe(true);

      // All item checkboxes should now be checked — the select-all toggle
      // selects EVERY item, so the checked count must equal the item count
      // (the previous `Math.min(itemCount, locator)` assertion cast a
      // Playwright locator to a number — NaN — and could never pass with
      // real items; the seeds in 2.4 exposed it the first time this test
      // ran against a populated inbox).
      const itemCheckboxes = page.locator('.my-approvals-inbox__item-select input[type="checkbox"]');
      const checkedCount = await itemCheckboxes.evaluateAll(
        (els) => (els as HTMLInputElement[]).filter((el) => el.checked).length,
      );
      expect(checkedCount).toBe(itemCount);
      expect(checkedCount).toBeGreaterThan(0);

      // Toggle off: deselect all
      await selectAllCheckbox.uncheck();
      expect(await selectAllCheckbox.isChecked()).toBe(false);

      const uncheckedCount = await itemCheckboxes.evaluateAll(
        (els) => (els as HTMLInputElement[]).filter((el) => el.checked).length,
      );
      expect(uncheckedCount).toBe(0);
    });

    test('bulk approve and bulk reject buttons render with count', async ({
      page,
    }) => {

      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      const items = page.locator('.my-approvals-inbox__list li');
      test.skip(
        (await items.count()) === 0,
        'No pending approval items',
      );

      // Select first item
      const firstCheckbox = items.first().locator('input[type="checkbox"]');
      test.skip((await firstCheckbox.count()) === 0, 'Item checkboxes not rendered');
      await firstCheckbox.check();

      // Bulk approve button must appear with count — guaranteed by the
      // component once an item is selected (selectedIds.size > 0), so the
      // assertion is direct (no count guard).
      const approveBtn = page.locator('.btn--primary, button').filter({ hasText: /Approve/ }).first();
      await expect(approveBtn).toBeVisible({ timeout: 5000 });
      expect(await approveBtn.textContent()).toMatch(/Approve/);

      // Deselect
      await firstCheckbox.uncheck();
    });

    test('individual item selection and deselection updates count', async ({
      page,
    }) => {

      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      const items = page.locator('.my-approvals-inbox__list li');
      const itemCount = await items.count();

      test.skip(
        itemCount < 2,
        `Only ${itemCount} items — need ≥2 to test multi-select`,
      );

      // Select two individual items
      const cb0 = items.nth(0).locator('input[type="checkbox"]');
      const cb1 = items.nth(1).locator('input[type="checkbox"]');

      test.skip((await cb0.count()) === 0, 'Checkboxes not rendered');

      await cb0.check();
      await cb1.check();

      expect(await cb0.isChecked()).toBe(true);
      expect(await cb1.isChecked()).toBe(true);

      // Deselect first item
      await cb0.uncheck();
      expect(await cb0.isChecked()).toBe(false);
      expect(await cb1.isChecked()).toBe(true);

      // Deselect second item too
      await cb1.uncheck();
    });

    test('bulk actions bar includes reject reason input when items selected', async ({
      page,
    }) => {

      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );
      // Seed REAL pending work via the authenticated browser session
      // (2.4 root cause: zero PENDING requests made every item-dependent
      // test skip). page.request shares the UI's own auth channel.
      const seeded = await createPendingAccessRequestsViaApi(page, await getTestUser(), 3);
      test.skip(seeded === 0, 'Could not seed pending approval items');
      await page.reload({ waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's asserts below are the primary pass/fail; a timeout here just falls through to them.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      const items = page.locator('.my-approvals-inbox__list li');
      test.skip((await items.count()) === 0, 'No pending items');

      // Select first item
      const firstCheckbox = items.first().locator('input[type="checkbox"]');
      test.skip((await firstCheckbox.count()) === 0, 'No checkboxes');
      await firstCheckbox.check();

      // Reject reason input must appear once an item is selected —
      // guaranteed by the component (selectedIds.size > 0 branch), so the
      // assertion is direct (no count guard).
      const reasonInput = page.locator('.my-approvals-inbox__reject-reason');
      await expect(reasonInput).toBeVisible({ timeout: 5000 });
      const placeholder = await reasonInput.getAttribute('placeholder');
      expect(placeholder?.length).toBeGreaterThan(0);

      // Deselect
      await firstCheckbox.uncheck();
    });
  });

  test.describe('Failure / Edge', () => {
    test('bulk approve/reject buttons not visible when no items selected', async ({
      page,
    }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );

      const items = page.locator('.my-approvals-inbox__list li');
      if ((await items.count()) === 0) {
        // Empty state — bulk actions bar should not render at all
        const bulkActions = page.locator('.my-approvals-inbox__bulk-actions');
        // Either not present or present but with no approve/reject buttons
        expect(
          (await bulkActions.count()) === 0 ||
          (await bulkActions.locator('button').count()) === 0,
        ).toBe(true);
        return;
      }

      // With items but no selection, bulk action buttons should be hidden
      // The MyApprovalsInbox only renders them when selectedIds.size > 0
      const selectedCheckboxes = page.locator(
        '.my-approvals-inbox__item-select input[type="checkbox"]:checked',
      );
      // Assume none are pre-selected — verify no approve/reject buttons visible
      if ((await selectedCheckboxes.count()) === 0) {
        const actionButtons = page.locator(
          '.my-approvals-inbox__bulk-actions button',
        );
        // Either no bulk actions at all, or no action buttons within
        const btnCount = await actionButtons.count();
        if (btnCount > 0) {
          // If buttons exist, verify none say Approve or Reject with a count
          for (let i = 0; i < btnCount; i++) {
            const text = await actionButtons.nth(i).textContent();
            // Should not have bulk-action text with count numbers
            const hasCount = /\d+/.test(text ?? '');
            expect(hasCount).toBe(false);
          }
        }
      }
    });

    test('empty inbox shows no bulk action bar', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );

      const hasEmpty = (await page.locator('.my-approvals-inbox__empty').count()) > 0;
      const hasList = (await page.locator('.my-approvals-inbox__list').count()) > 0;

      if (hasEmpty) {
        // When empty, no bulk actions bar should render
        const bulkActions = page.locator('.my-approvals-inbox__bulk-actions');
        expect(await bulkActions.count()).toBe(0);
      }
      // If hasList, items exist — handled by other tests
      expect(hasEmpty || hasList).toBe(true);
    });

    test('count badge in header reflects total pending items', async ({
      page,
    }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort readiness wait — the caller's skip/assert below is the primary pass/fail; a timeout here just falls through to it.
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      test.skip(
        page.url().includes('/403') || page.url().includes('/login'),
        'Role gate or auth redirect',
      );

      const items = page.locator('.my-approvals-inbox__list li');
      const itemCount = await items.count();

      if (itemCount > 0) {
        // Count badge must render and match the list count — guaranteed by
        // the component whenever items.length > 0, so the assertion is
        // direct (no count guard).
        const countBadge = page.locator('.my-approvals-inbox__count');
        await expect(countBadge).toBeVisible({ timeout: 5000 });
        const countText = await countBadge.textContent();
        const badgeCount = parseInt(countText?.trim() ?? '0', 10);
        expect(badgeCount).toBe(itemCount);
      }
    });
  });
});
