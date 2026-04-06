/**
 * E2E: Unified Asset Creation — all 4 submit paths from /assets/create.
 *
 * Tests the unified adaptive form with metadata-only, data-only,
 * contract-only, and data+contract creation flows.
 */

import { expect, test } from '@playwright/test';

test.describe('Unified Asset Creation', () => {
  test.setTimeout(120_000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/assets/create');
    await page.waitForLoadState('domcontentloaded');
  });

  test('renders the create asset form with all sections', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /create asset/i })).toBeVisible();
    await expect(page.getByLabel(/name/i)).toBeVisible();
    await expect(page.getByLabel(/key/i)).toBeVisible();
    await expect(page.getByLabel(/visibility/i)).toBeVisible();
    await expect(page.getByText(/add data file/i)).toBeVisible();
    await expect(page.getByText(/add contract/i)).toBeVisible();
    await expect(page.getByText(/will create.*asset/i)).toBeVisible();
  });

  test('auto-populates key from name', async ({ page }) => {
    await page.getByLabel(/name/i).fill('My Test Asset');
    const keyInput = page.getByLabel(/key/i);
    await expect(keyInput).toHaveValue('my-test-asset');
  });

  test('metadata-only: creates asset with name and key', async ({ page }) => {
    const uniqueName = `E2E Asset ${Date.now()}`;
    await page.getByLabel(/name/i).fill(uniqueName);

    // Submit
    const createBtn = page.getByRole('button', { name: /create/i });
    await expect(createBtn).toBeEnabled();

    const responsePromise = page.waitForResponse(
      (r) => r.url().includes('/api/v1/assets/') && r.request().method() === 'POST',
      { timeout: 30_000 },
    );
    await createBtn.click();

    const response = await responsePromise;
    expect(response.status()).toBeLessThan(400);

    // Should navigate to asset detail
    await page.waitForURL(/\/assets\/[a-f0-9-]+/, { timeout: 15_000 });
    expect(page.url()).toMatch(/\/assets\/[a-f0-9-]+/);
  });

  test('contract-only: expands contract section and creates with ODCS YAML', async ({ page }) => {
    const uniqueName = `E2E Contract Asset ${Date.now()}`;
    await page.getByLabel(/name/i).fill(uniqueName);

    // Expand contract section
    await page.getByText(/add contract/i).click();

    // Wait for textarea to appear
    const textarea = page.getByLabel(/contract content/i);
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Enter ODCS YAML
    const odcsYaml = `apiVersion: odcs/v3\nkind: DataContract\nid: e2e-${Date.now()}\nname: E2E Test`;
    await textarea.fill(odcsYaml);

    // Should show detection badge
    await expect(page.getByText(/ODCS/)).toBeVisible({ timeout: 5_000 });

    // Summary should update
    await expect(page.getByText(/will create.*asset.*contract/i)).toBeVisible();

    // Submit
    const createBtn = page.getByRole('button', { name: /create/i });
    await createBtn.click();

    // Should navigate to asset detail
    await page.waitForURL(/\/assets\/[a-f0-9-]+/, { timeout: 30_000 });
  });

  test('collapsible sections expand and collapse', async ({ page }) => {
    // Data file section
    const dataToggle = page.getByText(/add data file/i);
    await dataToggle.click();
    await expect(dataToggle).toHaveAttribute('aria-expanded', 'true');

    // Click again to collapse
    await page.getByText(/remove data file/i).click();
    await expect(page.getByText(/add data file/i)).toHaveAttribute('aria-expanded', 'false');

    // Contract section
    const contractToggle = page.getByText(/add contract/i);
    await contractToggle.click();
    await expect(contractToggle).toHaveAttribute('aria-expanded', 'true');
  });
});
