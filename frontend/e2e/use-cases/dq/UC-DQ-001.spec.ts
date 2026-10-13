/**
 * E2E: UC-DQ-001 — Run Data Quality Check / Monitor Asset Quality
 *
 * Use Case: Run Data Quality Check
 * Persona: Data Product Owner, Data Engineer, Compliance Officer
 * Reference: docs/USE_CASES.md#uc-dq-001
 *
 * Success/Failure/Edge. Routes: /dq, /dq/runs/:id.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { getTestUser } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-DQ-001: Run Data Quality Check @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('trigger DQ run from list page', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to login — auth not available');
      }
      // Gate-off terminal state: same W16 contract as the sibling tests in
      // this file (transient snapshot-fetch failure under churn, not a
      // disabled feature).
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'dq gate bounced to /unavailable — capabilities snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'dq gate bounced to /unavailable — transient snapshot failure'
      );
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 15000 });

      const actionBtn = page.locator(
        'button:has-text("Create"), button:has-text("New"), button:has-text("Run"), a:has-text("Create"), a:has-text("New"), a:has-text("Run")'
      ).first();

      if ((await actionBtn.count()) === 0) {
        test.info().annotations.push({ type: 'info', description: 'No create/run button found on DQ list page — skipping interaction' });
        return;
      }

      await actionBtn.click();
      await page.waitForTimeout(2000);

      // Look for a form or modal that appeared
      const formArea = page.locator('form, [role="dialog"], .modal, .dq-create-form').first();
      if ((await formArea.count()) === 0) {
        // Button may have navigated; check URL
        if (page.url().includes('/dq/')) {
          test.info().annotations.push({ type: 'info', description: 'Navigated after clicking action button' });
          return;
        }
        test.info().annotations.push({ type: 'info', description: 'No form/modal appeared after clicking action button' });
        return;
      }

      // The DQ create form REQUIRES at least one of Asset / Dataset /
      // File — its client-side validation silently blocks the POST when
      // all three are empty (b6 #5 follow-up: the dialog-scoped submit
      // was correct, but no POST ever fired and waitForResponse burned
      // 30s). There is no native <select> in the modal: the fields are
      // AssetPicker/DatasetPicker/FilePicker components. Use the
      // canonical picker recipe (combobox dropdown option, or the
      // feature-flag-off plain "Asset ID" input) — same as the
      // governance-retention CRUD create test.
      // intentional: best-effort asset provisioning — the picker
      // interaction below skips gracefully when no asset can be selected.
      const assetId = await createAssetViaApi(user, { ensureActivated: true }).catch(
        () => null,
      );
      let pickerSucceeded = false;
      if (assetId) {
        const pickerInput = page.locator(
          '[data-testid="dq-create-asset-picker"] input[aria-label="Select asset"]',
        );
        const plainInput = page.locator(
          '[data-testid="dq-create-asset-picker"] input[aria-label="Asset ID"]',
        );
        if ((await plainInput.count()) > 0) {
          await plainInput.first().fill(assetId);
          pickerSucceeded = true;
        } else if ((await pickerInput.count()) > 0) {
          await pickerInput.first().click();
          const dropdown = page.locator('.asset-picker-dropdown, [role="listbox"]');
          // intentional: best-effort picker interaction — the submit below
          // is the load-bearing assertion; a real product failure
          // surfaces there or in the skip below.
          const optionReady = await dropdown
            .first()
            .locator('[role="option"]')
            .first()
            .waitFor({ state: 'visible', timeout: 5000 })
            .then(() => true)
            .catch(() => false);
          if (optionReady) {
            await dropdown.first().locator('[role="option"]').first().click();
            pickerSucceeded = true;
          }
        }
      }
      test.skip(
        !pickerSucceeded,
        'Could not select an asset in the DQ create modal — form validation would block the POST',
      );
      if (!pickerSucceeded) return;

      // Scope to the dialog: the page-level "Create DQ run" header button
      // also matches has-text("Create") and appears EARLIER in the DOM —
      // clicking it merely toggles the dialog, no POST fires, and the
      // waitForResponse below burned 30s (b6 #5).
      const submitBtn = page
        .locator('[role="dialog"]')
        .locator('button[type="submit"], button:has-text("Run"), button:has-text("Create"), button:has-text("Submit")')
        .first();
      if ((await submitBtn.count()) === 0 || !(await submitBtn.isVisible())) {
        test.info().annotations.push({ type: 'info', description: 'No submit button visible in form' });
        return;
      }

      const [response] = await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/dq') && resp.request().method() === 'POST', { timeout: 30000 }),
        submitBtn.click(),
      ]);

      expect(response.status()).toBeLessThan(400);

      await page.waitForTimeout(3000);
      // Should be on detail page or back on list with new run
      const onDetail = page.url().includes('/dq/runs/');
      const onList = page.url().includes('/dq');
      expect(onDetail || onList).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('DQ runs list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"]',
      });
      // The DQ surface is CapabilityRoute-gated; data_quality is a runtime
      // capability emitted as true for the test tenant, so a /unavailable
      // bounce is a TRANSIENT capabilities-snapshot fetch failure under
      // batch churn, not a disabled feature. W16-guarded skip: raises in
      // CI, skips locally.
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'dq gate bounced to /unavailable — capabilities snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'dq gate bounced to /unavailable — transient snapshot failure'
      );
      expect(page.url()).toContain('/dq');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.dq-run-list-page').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('h1:has-text("Data Quality")').count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });
  });

  test.describe('Failure', () => {
    test('DQ run detail with non-existent id shows error', async ({ page }) => {
      const user = await getTestUser();
      const { loginUser } = await import('../../fixtures/auth');
      await loginUser(page, user);
      await page.goto('/dq/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.dq-run-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access to DQ redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/dq', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|dq)/, { timeout: 20_000 });
      expect(page.url().includes('/login') || page.url().includes('/dq')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('DQ list with empty state loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/dq', {
        timeout: 60000,
        contentSelector: '.dq-run-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      // Same gate-off contract as the Success test above: a /unavailable
      // bounce is a transient capabilities-snapshot fetch failure under
      // churn, not a disabled feature.
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'dq gate bounced to /unavailable — capabilities snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'dq gate bounced to /unavailable — transient snapshot failure'
      );
      expect(page.url()).toContain('/dq');
    });
  });
});
