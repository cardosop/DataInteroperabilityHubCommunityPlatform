/**
 * E2E Test: Dataset Creation Flow
 * Independent test for dataset creation (extracted from complete journey)
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('Dataset Creation Flow', () => {
  test.setTimeout(300000); // 5 min: visible/slowMo; file upload + create can be slow

  test.describe('Failure', () => {
    test('unauthenticated access to datasets create redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/datasets/create', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|datasets|register)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onDatasetsWithLoginPrompt =
        url.includes('/datasets') &&
        (await hasLoginPrompt(page));
      expect(onLogin || onDatasetsWithLoginPrompt).toBe(true);
    });
  });

  test('should create dataset with file upload', async ({ page }) => {
    test.setTimeout(300000); // Override chromium-routes --timeout=120000; file upload + 429 retries need headroom
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/datasets/create', {
      timeout: 90000,
      contentSelector: '.dataset-create-page, .error-display, .loading-spinner-container, .file-upload, h1',
    });
    await waitForLoadingComplete(page);

    // Wait for create page to load - use first() to avoid strict mode violation
    await expect(
      page.locator('.dataset-create-page').or(page.locator('h1:has-text("Create Dataset")')).first()
    ).toBeVisible({
      timeout: 10000,
    });

    // Upload file if dropzone present - handle rate limiting (429)
    const dropzone = page.locator('.file-upload-dropzone');
    if ((await dropzone.count()) > 0) {
      await expect(dropzone.first()).toBeVisible({ timeout: 10000 });
      await dropzone.first().click();
      await new Promise((r) => setTimeout(r, 500));

      const fileInput = page.locator('input[type="file"]');
      if ((await fileInput.count()) > 0) {
        // Upload file with retry on rate limit (429) - parse retry-after from error message
        let uploadSuccess = false;
        let retries = 0;
        const maxRetries = 5;

        while (!uploadSuccess && retries < maxRetries) {
          try {
            await fileInput.first().setInputFiles({
              name: 'test.csv',
              mimeType: 'text/csv',
              buffer: Buffer.from('name,age\nJohn,30\nJane,25'),
            });

            // Wait for upload response (may be success or 429)
            const response = await page
              .waitForResponse(
                (resp) =>
                  resp.url().includes('/files/') &&
                  (resp.status() === 200 || resp.status() === 201 || resp.status() === 429),
                { timeout: 30000 }
              )
              .catch(() => null);

            if (response && response.status() === 429) {
              // Rate limited - parse retry-after from error message
              // Backend: "retry after 6 seconds"; burst window 10s; use at least 10s
              let retryAfter = 10;
              try {
                const responseBody = await response.json().catch(() => ({}));
                const message =
                  (responseBody as { message?: string }).message ||
                  (typeof responseBody === 'string' ? responseBody : '');
                const retryMatch = message.match(/retry after (\d+) seconds?/i);
                if (retryMatch) {
                  retryAfter = Math.max(10, parseInt(retryMatch[1], 10) + 1);
                }
              } catch {
                // Use default
              }
              console.log(
                `File upload rate limited (429), waiting ${retryAfter}s before retry ${retries + 1}/${maxRetries}`
              );
              await new Promise((r) => setTimeout(r, retryAfter * 1000));
              retries++;
              continue;
            }

            // Wait for file to be processed (success indicator)
            await expect(
              page.locator('.file-upload-success, .upload-success').first()
            ).toBeVisible({
              timeout: 30000,
            });
            uploadSuccess = true;
          } catch (error) {
            // Check if it's a rate limit error from console
            const consoleErrors = await page
              .evaluate(() => {
                return Array.from(document.querySelectorAll('.error-message, .error-display'))
                  .map((el) => el.textContent)
                  .join(' ');
              })
              .catch(() => '');

            if (consoleErrors.includes('rate limit') || consoleErrors.includes('429')) {
              if (retries < maxRetries - 1) {
                const retryAfter = 10; // Wait longer on error
                console.log(
                  `File upload rate limited (from error), waiting ${retryAfter}s before retry ${retries + 1}/${maxRetries}`
                );
                await new Promise((r) => setTimeout(r, retryAfter * 1000));
                retries++;
                continue;
              }
            }

            if (retries < maxRetries - 1) {
              console.log(`File upload attempt ${retries + 1} failed, retrying...`);
              await new Promise((r) => setTimeout(r, 2000));
              retries++;
            } else {
              throw error;
            }
          }
        }
      }
    }

    // Fill dataset form
    const nameInput = page.locator('input[id="name"]');
    if ((await nameInput.count()) > 0) {
      await expect(nameInput).toBeVisible({ timeout: 10000 });
      await nameInput.fill(`test-dataset-${Date.now()}`);
    }

    // Submit
    const submitButton = page.locator('button:has-text("Create Dataset")');
    await expect(submitButton).toBeVisible({ timeout: 10000 });
    await submitButton.click();

    // Wait for redirect to detail page
    await expect(page).toHaveURL(/\/datasets\/[^/]+$/, { timeout: 15000 });
    // API can be slow under Docker/parallel load; wait for loading to finish then detail
    await waitForLoadingComplete(page, { timeout: 35000 });
    await page.waitForSelector(
      '.dataset-detail-page, .dataset-detail-content, .dataset-detail-metadata, .error-display, .empty-state',
      { timeout: 25000 }
    );
    const hasError = (await page.locator('.error-display').count()) > 0;
    if (hasError) {
      const errText = (await page.locator('.error-display').first().textContent()) ?? '';
      throw new Error(`Dataset creation failed: ${errText.slice(0, 300)}`);
    }
    await expect(
      page.locator('.dataset-detail-page, .dataset-detail-content, .dataset-detail-metadata').first()
    ).toBeVisible({ timeout: 5000 });
  });
});
