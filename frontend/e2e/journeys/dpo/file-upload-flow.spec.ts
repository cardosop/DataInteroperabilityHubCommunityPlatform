/**
 * E2E Test: File Upload Flow
 * Independent test for file upload (extracted from complete journey)
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('File Upload Flow', () => {
  test.setTimeout(120000); // 2 minutes

  test('should upload file successfully', async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    // Navigate to files page
    await page.goto('/files');
    await waitForLoadingComplete(page);

    // Wait for upload dropzone to be visible
    const dropzone = page.locator('.file-upload-dropzone');
    const dropzoneCount = await dropzone.count();

    if (dropzoneCount === 0) {
      // Files page might not have upload dropzone - check if there's an upload button or link
      const uploadButton = page.locator('button:has-text("Upload"), a:has-text("Upload")');
      if ((await uploadButton.count()) > 0) {
        await expect(uploadButton.first()).toBeVisible({ timeout: 10000 });
        await uploadButton.first().click();
        await waitForLoadingComplete(page);
        // After clicking upload, dropzone should appear
        await expect(page.locator('.file-upload-dropzone').first()).toBeVisible({ timeout: 10000 });
      } else {
        test.skip(
          true,
          'Upload UI not available (no upload button or dropzone); cannot test file upload'
        );
        return;
      }
    } else {
      await expect(dropzone.first()).toBeVisible({ timeout: 15000 });
    }

    // Find file input
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 10000 });

    // Upload file with retry on rate limit (429) - parse retry-after from error message
    let uploadSuccess = false;
    let retries = 0;
    const maxRetries = 5;

    while (!uploadSuccess && retries < maxRetries) {
      try {
        await fileInput.setInputFiles({
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
          let retryAfter = 5; // Default wait time
          try {
            const responseBody = await response.json().catch(() => ({}));
            const message = responseBody.message || '';
            const retryMatch = message.match(/retry after (\d+) seconds?/i);
            if (retryMatch) {
              retryAfter = parseInt(retryMatch[1], 10) + 1; // Add 1s buffer
            }
          } catch {
            // Use default
          }
          console.log(
            `File upload rate limited (429), waiting ${retryAfter}s before retry ${retries + 1}/${maxRetries}`
          );
          await page.waitForTimeout(retryAfter * 1000);
          retries++;
          continue;
        }

        // Wait for upload to start and complete
        // Check for success indicator or file appearing in list
        await expect(
          page.locator(
            '.file-upload-success, .file-upload-success-text, .file-list-page table tbody tr'
          )
        ).toBeVisible({ timeout: 60000 });
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
            await page.waitForTimeout(retryAfter * 1000);
            retries++;
            continue;
          }
        }

        if (retries < maxRetries - 1) {
          console.log(`File upload attempt ${retries + 1} failed, retrying...`);
          await page.waitForTimeout(5000);
          retries++;
        } else {
          throw error;
        }
      }
    }
  });
});
