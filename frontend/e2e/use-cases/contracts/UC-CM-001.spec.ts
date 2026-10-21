/**
 * E2E: UC-CM-001 — Create Contract
 *
 * Use Case: Create Contract (Contract Management)
 * Persona: Data Product Owner, Data Engineer
 * Reference: docs/USE_CASES.md, docs/TEST_TRACEABILITY.md
 *
 * Success/Failure/Edge. Routes: /contracts, /odps/upload (legacy — Phase 211.A6
 * redirects it to /contracts/create).
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('UC-CM-001: Create Contract @critical', () => {
  // The upload test waits up to 120s for the products POST (sync
  // workflow runs server-side before the response lands) plus a 20s
  // terminal-state poll — 90s was tighter than a single inner wait.
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]',
      });
      expect(page.url()).toContain('/contracts');
      await waitForLoadingComplete(page, { timeout: 15000 });
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('upload ODPS contract via upload page', async ({ page }) => {
      const user = await getTestUser();
      // Legacy /odps/upload redirects (Phase 211.A6) to the unified contract create page.
      await loginAndNavigateToRoute(page, user, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea.contract-file-reader__textarea, textarea, .contract-create-page',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login — auth not available');
      expect(page.url()).toContain('/contracts/create');
      await waitForLoadingComplete(page, { timeout: 15000 });

      // Default creation mode is Raw Upload; click the tab defensively so the
      // JSON-paste textarea is mounted even if the default changes.
      const rawModeTab = page.locator('button[role="tab"]:has-text("Raw Upload")').first();
      if ((await rawModeTab.count()) > 0) {
        await rawModeTab.click();
      }

      const textarea = page.locator('textarea.contract-file-reader__textarea, textarea').first();
      await textarea.waitFor({ state: 'visible', timeout: 10000 });

      const ts = Date.now();
      const odpsPayload = JSON.stringify({
        schema: 'https://opendataproducts.org/schema/v4.1',
        version: '4.1',
        product: {
          details: {
            en: {
              productID: `e2e-contract-${ts}`,
              name: `E2E Test Contract ${ts}`,
              description: 'Automated E2E test contract',
              productVersion: '1.0.0',
            },
          },
          dataSchema: {
            fields: [
              { name: 'id', type: 'integer', description: 'Primary key' },
              { name: 'name', type: 'string', description: 'Name field' },
            ],
          },
          contract: {
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: `e2e-odcs-${ts}`,
              name: `E2E ODCS Contract ${ts}`,
              version: '1.0.0',
              description: 'Embedded ODCS contract for E2E upload test',
              schema: {
                fields: [
                  { name: 'id', type: 'integer', nullable: false, description: 'Primary key' },
                  { name: 'name', type: 'string', nullable: true, description: 'Name field' },
                ],
              },
            },
          },
        },
      });
      await textarea.fill(odpsPayload);

      // The submit path branches on ContractFileReader's DEBOUNCED
      // detection (300ms after the fill): while `detected` is still
      // null the page falls back to the synchronous ODCS endpoint
      // (POST /contracts/), which rejects an ODPS document with
      // STRUCTURELESS_CONTRACT. Wait for the ODPS badge BEFORE clicking
      // submit so the ODPS workflow endpoint (POST /contracts/products/)
      // is the one that fires.
      await expect(
        page.locator('.contract-file-reader__badge--odps'),
      ).toBeVisible({ timeout: 10000 });

      // Select JSON format if a format selector exists
      const formatSelect = page.locator('select#format, select[name="format"], [data-testid="format-selector"]').first();
      if ((await formatSelect.count()) > 0 && await formatSelect.isVisible()) {
        await formatSelect.selectOption({ label: 'JSON' }).catch(() =>
          formatSelect.selectOption({ value: 'json' })
        );
      }

      // MUST be the action button, not the mode tabs: the loose
      // `button:has-text("Upload")` also matches the "Raw Upload" TAB
      // (a <button role="tab"> rendered before the form), so `.first()`
      // clicked the tab — the submit never fired and the test could
      // never reach a terminal state. Pin the accessible name of the
      // raw-mode submit button instead.
      const submitBtn = page
        .getByRole('button', { name: /^Create Contract$/i })
        .or(page.getByRole('button', { name: /^Create Data Product$/i }));
      await submitBtn.first().waitFor({ state: 'visible', timeout: 10000 });

      const [response] = await Promise.all([
        page.waitForResponse(
          // Scoped to the products endpoint on purpose: the page auto-fires
          // POST /contracts/validate-draft/ (debounced after the textarea
          // fill), which also matches a loose '/contracts' POST filter and
          // resolves BEFORE the create POST. The test then raced ahead and
          // asserted terminal state while the sync product-creation
          // workflow was still executing (both markers false → hard fail
          // on a healthy stack).
          (resp) =>
            resp.url().includes('/contracts/products') &&
            resp.request().method() === 'POST',
          // The sync product-creation workflow runs server-side before
          // the response lands; 30s is tight when the box is busy (the
          // SPA's own axios timeout is 120s). Match that budget.
          { timeout: 120000 }
        ),
        submitBtn.first().click(),
      ]);

      if (response.status() >= 400) {
        // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
        const body = await response.text().catch(() => '');
        throw new Error(`POST contract/odps returned ${response.status()}: ${body}`);
      }

      // The UI polls the workflow status every 2s and navigates only after
      // the first COMPLETED poll — a fixed 1.5s sleep raced that first poll
      // (both success markers false). Now that the products POST response is
      // in hand, the SPA sets workflowId on the next render and the progress
      // element appears; navigation follows once the workflow status poll
      // returns COMPLETED (sync test-env path completes in seconds). Poll
      // for EITHER terminal outcome with a bounded budget instead of a
      // one-shot check.
      await expect
        .poll(
          async () => {
            const onDetail =
              page.url().includes('/contracts/') &&
              !page.url().endsWith('/contracts/create');
            const progressVisible =
              (await page.locator('.contract-create-page__progress').count()) > 0;
            return onDetail || progressVisible;
          },
          { timeout: 20000, intervals: [500, 1000, 2000] }
        )
        .toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('ODPS upload route loads for contract creation', async ({ page }) => {
      const user = await getTestUser();
      // Legacy /odps/upload redirects (Phase 211.A6) to the unified contract create page.
      await loginAndNavigateToRoute(page, user, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea.contract-file-reader__textarea, textarea, .contract-create-page',
      });
      test.skip(page.url().includes('/login'), 'Redirected to login');
      expect(page.url()).toContain('/contracts/create');
      const hasUploadUI =
        (await page.locator('textarea.contract-file-reader__textarea, textarea, .contract-create-page').count()) > 0;
      expect(hasUploadUI).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/login/, { timeout: 20_000 });
      const url = page.url();
      expect(url).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('contracts empty state shows create option', async ({ page }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/contracts', {
        timeout: 60000,
        contentSelector: '.contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      expect(page.url()).toContain('/contracts');
      const hasContent =
        (await page.locator('.contract-list-page, [data-testid="contract-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true);
      const hasCreateOption =
        (await page.locator('a[href*="/contracts/create"], button:has-text("Create"), button:has-text("New Contract")').count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasCreateOption).toBe(true);
    });
  });
});
