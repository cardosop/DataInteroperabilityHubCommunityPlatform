/**
 * E2E: Contract Auto-Detection — verify detection badge for different spec types.
 *
 * Tests that pasting ODPS YAML, ODCS JSON, and unknown content
 * shows the correct detection badge in real-time.
 */

import { expect, test } from '@playwright/test';

test.describe('Contract Auto-Detection', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/contracts/create');
    await page.waitForLoadState('domcontentloaded');
  });

  test('detects ODCS YAML and shows badge', async ({ page }) => {
    const textarea = page.getByLabel(/contract content/i);
    await expect(textarea).toBeVisible();

    const odcsYaml = [
      'apiVersion: odcs/v3',
      'kind: DataContract',
      'id: test-detection',
      'name: Detection Test',
    ].join('\n');

    await textarea.fill(odcsYaml);

    // Badge should appear
    await expect(page.getByText(/ODCS/)).toBeVisible({ timeout: 5_000 });
  });

  test('detects ODPS JSON and shows badge', async ({ page }) => {
    const textarea = page.getByLabel(/contract content/i);

    const odpsJson = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v4.1',
      version: '4.1',
      product: { details: { en: { productID: 'test', name: 'Test' } } },
    });

    await textarea.fill(odpsJson);

    await expect(page.getByText(/ODPS/)).toBeVisible({ timeout: 5_000 });
  });

  test('shows no badge for unknown content', async ({ page }) => {
    const textarea = page.getByLabel(/contract content/i);

    await textarea.fill('foo: bar\nbaz: 123');

    // Wait for debounce
    await page.waitForTimeout(500);

    // Should NOT show any spec type badge
    await expect(page.getByText(/Detected:/)).not.toBeVisible();
  });

  test('clears badge when content is cleared', async ({ page }) => {
    const textarea = page.getByLabel(/contract content/i);

    // First, add ODCS content
    await textarea.fill('apiVersion: odcs/v3\nkind: DataContract\nid: test');
    await expect(page.getByText(/ODCS/)).toBeVisible({ timeout: 5_000 });

    // Clear content
    await textarea.fill('');

    // Badge should disappear
    await expect(page.getByText(/ODCS/)).not.toBeVisible({ timeout: 5_000 });
  });
});
