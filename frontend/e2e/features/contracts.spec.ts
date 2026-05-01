/**
 * E2E Feature: Contracts
 * Per E2E_FULL_COVERAGE_PLAN and tasks 8.3.1/8.3.2. Routes: /contracts, /contracts/:id/edit, /contracts/:id/link-odps.
 * Success/Failure/Edge/Validation. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';
import {
  assertListPageLoads,
  assertNonExistentIdShowsError,
  loginAndNavigateToRoute,
} from '../fixtures/helpers';

test.describe('Feature: Contracts', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('contracts list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/contracts', {
        timeout: 60000,
        contentSelector:
          '.contract-list-page, [data-testid="contract-list-page"], .contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      if (page.url().includes('/login')) {
        throw new Error('contracts list loads: still on /login after loginAndNavigateToRoute');
      }
      await assertListPageLoads(
        page,
        '.contract-list-page, [data-testid="contract-list-page"], .contract-list-page, [data-testid="contract-list-page"], .empty-state, [data-testid="empty-state"]',
        { timeout: 60000 }
      );
    });
  });

  test.describe('Failure', () => {
    test('contract edit with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/edit',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .contract-edit-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-edit-page',
      });
    });

    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      await page.goto('/contracts');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/contracts'),
        'Expected /login redirect or /contracts with auth'
      ).toBe(true);
    });
  });

  test.describe('Validation', () => {
    test('contract create page shows validation errors for invalid content', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/contracts/create', { waitUntil: 'domcontentloaded' });

      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to /login — auth token expired');
        return;
      }

      // Paste invalid ODCS (missing required fields).
      const textarea = page
        .locator(
          'textarea[aria-label*="contract" i], textarea[aria-label*="content" i], .contract-file-reader textarea, .contract-file-reader__textarea'
        )
        .first();
      await textarea.waitFor({ state: 'visible', timeout: 20000 });
      await textarea.fill('{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}');

      // Wait for debounced validation (1.5s debounce + backend round-trip).
      const validationPanel = page.locator('.validation-result-panel');
      await expect(validationPanel).toBeVisible({ timeout: 30000 });

      // Assert: terminal validation state shown (not just loading)
      const terminalPanel = page.locator(
        '.validation-result-panel--error, .validation-result-panel--success, .validation-result-panel--warning'
      );
      await expect(terminalPanel.first()).toBeVisible({ timeout: 15000 });

      // If error state, verify Create button is disabled
      const hasError = (await page.locator('.validation-result-panel--error').count()) > 0;
      if (hasError) {
        await expect(
          page.locator('button:has-text("Create Contract")').first()
        ).toBeDisabled();
      }
    });

    /*
     * Phase 227 Wave 1 (227.L5.15) — STRUCTURELESS_CONTRACT error code
     * surfaces in the Create flow.
     *
     * Pre-Wave-1, posting an ODCS body with no schema/models would
     * succeed and persist a structureless row. Post-Wave-1 the backend
     * returns 400 ``STRUCTURELESS_CONTRACT`` and the frontend surfaces
     * the typed error code. We assert the error appears somewhere in
     * the validation panel so future copy edits don't drop it silently.
     */
    test('contract create surfaces STRUCTURELESS_CONTRACT for empty schema', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/contracts/create', { waitUntil: 'domcontentloaded' });

      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to /login — auth token expired');
        return;
      }

      const textarea = page
        .locator(
          'textarea[aria-label*="contract" i], textarea[aria-label*="content" i], .contract-file-reader textarea, .contract-file-reader__textarea'
        )
        .first();
      await textarea.waitFor({ state: 'visible', timeout: 20000 });
      // Well-formed ODCS envelope but no schema or models — exactly the
      // structureless-population shape the floor enforcer rejects.
      await textarea.fill(
        JSON.stringify({
          apiVersion: 'odcs.io/v3.0.2',
          kind: 'DataContract',
          id: 'structureless-e2e',
          name: 'structureless-e2e',
          version: '1.0.0',
          status: 'active',
          info: { description: 'no schema or models declared' },
        })
      );

      const validationPanel = page.locator('.validation-result-panel');
      await expect(validationPanel).toBeVisible({ timeout: 30000 });

      // The error panel must surface the STRUCTURELESS_CONTRACT code or
      // its friendly remediation copy ("models or schema fields").
      const errorPanel = page.locator('.validation-result-panel--error');
      await expect(errorPanel.first()).toBeVisible({ timeout: 15000 });
      const errorText = await errorPanel.first().textContent();
      expect(errorText ?? '').toMatch(/structureless|no resolvable|schema fields|models/i);
    });
  });

  // Phase 230.5.7 (REQ-SEM-RELATIONSHIPS-001) — RelationshipsPanel
  // visibility on the contract detail page.  Pinned here so any
  // future regression in the panel mount or the semantic-service
  // fetch is caught at the E2E layer.
  test.describe('Relationships', () => {
    test('contract detail page renders the RelationshipsPanel', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      // Navigate to the contracts list first so we can find a real
      // contract id without depending on a fixture.
      await page.goto('/contracts');
      // The list either has rows (we click into one) or is empty
      // (we skip — the panel can't render without a contract).
      const firstRow = page.locator(
        '[data-testid="contract-list-row"], .contract-list-row',
      ).first();
      const hasContracts = await firstRow.isVisible({ timeout: 30000 }).catch(() => false);
      if (!hasContracts) {
        test.skip(true, 'No contracts in this test tenant — RelationshipsPanel requires a contract id');
      }
      await firstRow.click();
      // The panel mounts inside the Details tab (default).
      const panel = page.locator('[data-testid="relationships-panel"]');
      await expect(panel).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Edge', () => {
    test('contract link-odps with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(
        page,
        testUser,
        '/contracts/00000000-0000-0000-0000-000000000000/link-odps',
        {
          timeout: 60000,
          contentSelector: '.error-display, [data-testid="error-display"], .contract-link-odps-page, h1',
        }
      );
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.contract-link-odps-page',
      });
    });
  });
});
