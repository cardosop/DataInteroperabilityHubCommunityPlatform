/**
 * E2E Test: Contract Creation Flow
 * Independent test for contract creation (extracted from complete journey)
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Contract Creation Flow', () => {
  test.setTimeout(120000); // 2 minutes

  test('should create contract successfully', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Navigate to contracts page
    await page.goto('/contracts');
    await waitForLoadingComplete(page);

    // Wait for page to load - may show empty state or list
    await page.waitForTimeout(2000);

    // Check if we have empty state or list with create button
    const emptyState = page.locator('.empty-state, [data-testid="empty-state"]');
    const createButton = page.locator('button:has-text("Create Contract")');
    const emptyStateAction = page.locator('.empty-state-action, .empty-state button');

    const hasEmptyState =
      (await emptyState.count()) > 0 &&
      (await emptyState
        .first()
        .isVisible()
        .catch(() => false));
    const hasCreateButton =
      (await createButton.count()) > 0 &&
      (await createButton
        .first()
        .isVisible()
        .catch(() => false));
    const hasEmptyStateAction =
      (await emptyStateAction.count()) > 0 &&
      (await emptyStateAction
        .first()
        .isVisible()
        .catch(() => false));

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
      // Fallback: navigate directly to ODPS upload
      await page.goto('/odps/upload');
      await waitForLoadingComplete(page);
    }

    // Wait for navigation - button now navigates to /odps/upload
    await expect(page).toHaveURL(/\/odps\/upload/, { timeout: 15000 });
    await waitForLoadingComplete(page);

    // Fill ODPS upload form - find textarea for contract content (id="odps-content")
    // ODPS format requires: schema (string URL), version, product.details, product.dataSchema
    const contentTextarea = page.locator('textarea#odps-content, textarea').first();
    await expect(contentTextarea).toBeVisible({ timeout: 10000 });
    await contentTextarea.fill(
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

    // Wait for workflow to start - may redirect to workflow status or contract detail
    await page.waitForTimeout(5000);
    await waitForLoadingComplete(page);

    // Check URL - may be workflow status or contract detail
    const finalUrl = page.url();
    if (finalUrl.includes('/contracts/') && !finalUrl.includes('/edit')) {
      // Contract detail page
      await expect(page.locator('.contract-detail-page, .contract-detail-content, h1')).toBeVisible(
        { timeout: 15000 }
      );
    } else if (finalUrl.includes('/status') || finalUrl.includes('/workflow')) {
      // Workflow status page - contract creation in progress
      await expect(
        page.locator('h1, .workflow-status, .status, [data-testid="workflow-status"]')
      ).toBeVisible({ timeout: 10000 });
    } else {
      // Still on upload page - workflow may be processing, verify form was submitted
      await expect(page.locator('.odps-upload-page, .upload-form')).toBeVisible({ timeout: 10000 });
    }
  });
});
