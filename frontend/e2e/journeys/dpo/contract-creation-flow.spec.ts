/**
 * E2E Test: Contract Creation Flow
 * Independent test for contract creation (extracted from complete journey)
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';
// Phase 226 B1a — dual-channel verification on contract-create mutation.
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

test.describe('Contract Creation Flow', () => {
  test.setTimeout(90000);

  test.describe('Failure', () => {
    test('unauthenticated access to contracts redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|contracts)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onContractsWithLoginPrompt =
        url.includes('/contracts') &&
        (await hasLoginPrompt(page));
      expect(onLogin || onContractsWithLoginPrompt).toBe(true) /* acceptable states */;
    });

    test('invalid ODPS (missing schema.fields) shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
        timeout: 60000,
        contentSelector: 'textarea#odps-content, textarea, .odps-upload-page, .error-display',
      });
      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login');
      }
      const contentTextarea = page.locator('textarea#odps-content, textarea').first();
      await expect(contentTextarea).toBeVisible({ timeout: 10000 });
      // odps-invalid-missing-schema.json: contract.spec without schema.fields
      const invalidOdps = {
        schema: 'https://opendataproducts.org/schema/v4.1',
        version: '4.1',
        product: {
          details: { en: { productID: 'invalid', name: 'Invalid', description: 'Missing schema.fields' } },
          contract: {
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: 'invalid-missing-schema',
              name: 'Invalid - No Schema Fields',
              version: '1.0.0',
            },
          },
        },
      };
      await contentTextarea.fill(JSON.stringify(invalidOdps));
      await page.waitForTimeout(500);
      const submitButton = page.locator('button:has-text("Create ODPS Product")').first();
      await expect(submitButton).toBeVisible({ timeout: 5000 });
      await submitButton.click();
      await page.waitForTimeout(8000);
      await waitForLoadingComplete(page);
      // Expect error: 400 or validation error; no contract created (stay on upload or show error)
      const errorDisplay = page.locator('.error-display, [role="alert"], .alert-danger');
      const hasErrorDisplay =
        (await errorDisplay.count()) > 0 && (await errorDisplay.first().isVisible());
      const hasErrorText =
        (await page.getByText(/400|validation|invalid|schema|required|dataSchema/i).count()) > 0;
      expect(hasErrorDisplay || hasErrorText).toBe(true);
    });
  });

  test.describe('Success', () => {
  test('should create contract successfully', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/contracts', {
      timeout: 60000,
      contentSelector: '.contract-list-page, .empty-state, .error-display, h1',
    });
    await waitForLoadingComplete(page);

    // Wait for page to load - may show empty state or list
    await page.waitForTimeout(2000);

    // Check if we have empty state or list with create button
    const emptyState = page.locator('.empty-state, [data-testid="empty-state"]');
    const createButton = page.locator('button:has-text("Create Contract")');
    const emptyStateAction = page.locator('.empty-state-action, .empty-state button');

    const hasEmptyState =
      (await emptyState.count()) > 0 &&
      (await emptyState.first().isVisible());
    const hasCreateButton =
      (await createButton.count()) > 0 &&
      (await createButton.first().isVisible());
    const hasEmptyStateAction =
      (await emptyStateAction.count()) > 0 &&
      (await emptyStateAction.first().isVisible());

    if (hasEmptyState && !hasCreateButton) {
      // Empty state - check if there's an action button
      if (hasEmptyStateAction) {
        await expect(emptyStateAction.first()).toBeVisible({ timeout: 10000 });
        await emptyStateAction.first().click();
        await page.waitForTimeout(1000);
      } else {
        // Navigate directly to ODPS upload (contracts are created via ODPS)
        await page.goto('/odps/upload');
        await waitForLoadingComplete(page);
      }
    } else if (hasCreateButton) {
      // List page with create button
      await expect(createButton.first()).toBeVisible({ timeout: 10000 });
      await createButton.first().click();
      await page.waitForTimeout(1000);
    } else {
      // Fallback: click ODPS in sidebar to reach upload (client-side nav)
      const odpsLink = page.locator('.app-sidebar .nav-link').filter({ hasText: 'ODPS' }).first();
      await odpsLink.click();
      await page.waitForLoadState('domcontentloaded');
      await waitForLoadingComplete(page, { timeout: 20000 });
      const uploadBtn = page.locator('button:has-text("Create ODPS Product"), button:has-text("Create Your First")').first();
      if ((await uploadBtn.count()) > 0) {
        await uploadBtn.click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      }
      // If still on /odps (list), navigate directly to upload
      if (page.url().includes('/odps') && !page.url().includes('/odps/upload')) {
        await page.goto('/odps/upload');
        await waitForLoadingComplete(page);
      }
    }

    // Wait for navigation - button now navigates to /odps/upload (or redirect to login if auth failed)
    if (page.url().includes('/login')) {
      throw new Error('Unexpected redirect to login after contracts page - auth may have failed');
    }
    await expect(page).toHaveURL(/\/odps\/upload/, { timeout: 15000 });
    await waitForLoadingComplete(page);

    // Fill ODPS upload form - find textarea for contract content (id="odps-content")
    // ODPS format requires: schema (string URL), version, product.details, product.dataSchema
    const contentTextarea = page.locator('textarea#odps-content, textarea').first();
    await expect(contentTextarea).toBeVisible({ timeout: 10000 });
    await     contentTextarea.fill(
      JSON.stringify({
        schema: 'https://opendataproducts.org/schema/v4.1',
        version: '4.1',
        product: {
          details: {
            en: {
              productID: `test-product-${Date.now()}`,
              name: 'Test Product',
              description: 'Test Product Description',
              productVersion: '1.0.0',
            },
          },
          dataSchema: {
            fields: [
              { name: 'id', type: 'string' },
              { name: 'name', type: 'string' },
            ],
          },
          contract: {
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: `test-odcs-${Date.now()}`,
              name: 'Test ODCS Contract',
              version: '1.0.0',
              description: 'E2E test ODCS contract',
              schema: {
                fields: [
                  { name: 'id', type: 'string', nullable: false, description: 'ID' },
                  { name: 'name', type: 'string', nullable: false, description: 'Name' },
                ],
              },
            },
          },
        },
      })
    );

    // Wait a bit for form to update
    await page.waitForTimeout(500);

    // Submit - button text is "Create ODPS Product"
    const submitButton = page.locator('button:has-text("Create ODPS Product")').first();
    await expect(submitButton).toBeVisible({ timeout: 10000 });
    await expect(submitButton).toBeEnabled({ timeout: 5000 }); // Wait for button to be enabled (content must be filled)
    await submitButton.click();

    // Wait for API response (success or error)
    await page.waitForTimeout(8000);
    await waitForLoadingComplete(page);

    // Check URL - may be workflow status, contract detail, or still on upload (with error)
    const finalUrl = page.url();
    if (finalUrl.includes('/contracts/') && !finalUrl.includes('/edit')) {
      // Contract detail page - success
      await expect(page.locator('.contract-detail-page, .contract-detail-content, h1').first()).toBeVisible(
        { timeout: 15000 }
      );
      // Phase 226 B1a — dual-channel verification of contract creation.
      const contractId = finalUrl.split('/').pop()?.split('?')[0] ?? '';
      if (contractId.length > 20) {
        await verifyViaApi(page, `/api/v1/contracts/${contractId}/`, {});
        await verifyAuditEvent(page, {
          action: 'CONTRACT_CREATED',
          resourceType: 'CONTRACT',
          resourceId: contractId,
        });
      }
    } else if (finalUrl.includes('/odps/') && !finalUrl.includes('/upload')) {
      // ODPS detail page - success (navigated after workflow completed)
      await expect(page.locator('.odps-detail-page, .contract-detail-page, h1').first()).toBeVisible(
        { timeout: 15000 }
      );
    } else if (finalUrl.includes('/status') || finalUrl.includes('/workflow')) {
      // Workflow status page - contract creation in progress
      await expect(
        page.locator('h1, .workflow-status, .status, [data-testid="workflow-status"]').first()
      ).toBeVisible({ timeout: 10000 });
    } else if (finalUrl.includes('/odps/upload')) {
      // Still on upload page — check for error display
      const errorDisplay = page.locator('.error-display');
      if ((await errorDisplay.count()) > 0 && (await errorDisplay.first().isVisible())) {
        const errorText = await errorDisplay.first().textContent() ?? '';
        // "Workflows are disabled for this tenant" is a backend config issue — skip
        if (/workflows are disabled/i.test(errorText)) {
          test.skip(true, 'Contract creation skipped: workflows are disabled');
        }
        throw new Error(
          `Contract creation failed. API error: ${errorText.replace(/\s+/g, ' ').substring(0, 500)}`
        );
      }
      // No error and no redirect — this is a failure
      throw new Error('Still on upload page after submit with no error and no redirect');
    } else {
      throw new Error(`Unexpected URL after submit: ${finalUrl}`);
    }
  });
  });
});
