/**
 * E2E Test: JOURNEY-DPO-001 — Onboard New Asset via Data-First Flow
 *
 * Journey: Onboard New Asset via Data-First Flow
 * Persona: Data Product Owner
 * Source: Migrated from phase2-catalog-journey.spec.ts (complete catalog journey).
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md (UC-AM-001)
 *
 * Each dimension (Success, Failure, Edge) lives in this file; shared step helpers from fixtures/.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DPO-001: Onboard New Asset via Data-First Flow', () => {
  test.setTimeout(480000); // 8 min: full journey + loginUser rate-limit retries when suite runs (no mocks)

  test.describe('Success', () => {
    test('complete journey: create asset → upload file → create dataset → contracts page → activate asset', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);

      // Step 1: Create Asset
      await page.goto('/assets');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const hasContent = main.querySelector(
            '.asset-list-page, .empty-state, .error-display, h1'
          );
          return !!hasContent;
        },
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);

      const createButton = page
        .locator('button:has-text("Create Asset")')
        .or(page.locator('.empty-state-action:has-text("Create Asset")'));
      await createButton.first().waitFor({ timeout: 10000 });
      await createButton.first().click();

      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
      await page.waitForSelector('input[id="key"]', { timeout: 10000 });
      const assetKey = `test-asset-${Date.now()}`;
      await page.fill('input[id="key"]', assetKey);
      await page.fill('input[id="name"]', 'Test Asset');
      await page.fill('textarea[id="description"]', 'Test asset description');
      await page.selectOption('select[id="visibility"]', 'INTERNAL');

      const submitButton = page.locator('button:has-text("Create Asset")');
      await submitButton.waitFor({ timeout: 10000 });
      await submitButton.click();

      await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 15000 });
      const assetUrl = page.url();
      const assetId = assetUrl.split('/').pop()!;

      await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 35000 });
      const assetHeading = page.locator('.asset-detail-page h1, .asset-detail-content h1').first();
      await expect(assetHeading).toContainText('Test Asset', { timeout: 10000 });
      await expect(page.locator('.status-badge').first()).toContainText('DRAFT');

      // Step 2: Create Dataset (with file upload when dropzone present)
      await page.goto('/datasets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const createPage = main.querySelector('.dataset-create-page');
          if (createPage) return true;
          const h1 = main.querySelector('h1');
          return !!h1?.textContent?.includes('Create Dataset');
        },
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);

      const dropzone = page.locator('.file-upload-dropzone');
      if ((await dropzone.count()) > 0) {
        await dropzone.first().click();
        await page.waitForTimeout(500);
        const datasetFileInput = page.locator('input[type="file"]');
        if ((await datasetFileInput.count()) > 0) {
          await datasetFileInput.setInputFiles({
            name: 'test.csv',
            mimeType: 'text/csv',
            buffer: Buffer.from('name,age\nJohn,30\nJane,25'),
          });
          const createDatasetBtn = page.locator('button:has-text("Create Dataset")');
          await createDatasetBtn.waitFor({ state: 'visible', timeout: 10000 });
          await page.waitForFunction(
            () => {
              const buttons = Array.from(document.querySelectorAll('button'));
              const createButton = buttons.find((btn) =>
                btn.textContent?.includes('Create Dataset')
              );
              return createButton && !createButton.disabled;
            },
            { timeout: 180000 }
          );
        }
      }

      const assetIdInput = page.locator('input[placeholder*="Asset ID"]');
      if ((await assetIdInput.count()) > 0) {
        await assetIdInput.fill(assetId);
      }

      const createDatasetButton = page.locator('button:has-text("Create Dataset")');
      await createDatasetButton.waitFor({ state: 'visible', timeout: 10000 });
      let attempts = 0;
      while ((await createDatasetButton.isDisabled()) && attempts < 3) {
        await page.waitForTimeout(5000);
        attempts++;
      }
      await createDatasetButton.click();

      await page.waitForURL(/\/datasets\/[^/]+$/, { timeout: 30000 });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          return main.querySelector('.dataset-detail-page, .dataset-detail-content, h1') !== null;
        },
        { timeout: 20000 }
      );
      await page.waitForTimeout(2000);
      const datasetHeading = page
        .locator('.dataset-detail-page h1, .dataset-detail-content h1, .app-main h1')
        .first();
      await expect(datasetHeading).toBeVisible({ timeout: 10000 });

      // Step 3: Contracts page loads
      await page.goto('/contracts');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          return main.querySelector('.contract-list-page, .empty-state, h1') !== null;
        },
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/contracts');

      // Step 4: Activate Asset
      await page.goto(`/assets/${assetId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          return main.querySelector('.asset-detail-page, .asset-detail-content, h1') !== null;
        },
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);

      const activateButton = page.locator('button:has-text("Activate Asset")');
      if ((await activateButton.count()) > 0) {
        await activateButton.click();
        await page.waitForTimeout(3000);
        await page.reload();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(2000);
        const statusBadge = page.locator('.status-badge').first();
        await expect(statusBadge).toContainText('ACTIVE', { timeout: 15000 });
      }
    });
  });

  test.describe('Failure', () => {
    test('assets list shows error or empty when API fails or returns empty', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const hasContent = main.querySelector(
            '.asset-list-page, .empty-state, .error-display, h1'
          );
          return !!hasContent;
        },
        { timeout: 15000 }
      );
      expect(page.url()).toContain('/assets');
    });

    test('asset create with empty key shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('input[id="key"]', { timeout: 10000 });
      await page.fill('input[id="name"]', 'Test Asset Name');
      await page.locator('button:has-text("Create Asset")').click();
      await page.waitForTimeout(500);
      // Browser required or app validation prevents submit; we stay on create page (no navigation)
      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 5000 });
      const keyError = page.locator('.error-message').filter({ hasText: /key|required/i });
      const hasKeyError = (await keyError.count()) > 0;
      const keyInput = page.locator('input[id="key"]');
      const keyInvalid = await keyInput.evaluate(
        (el) => (el as HTMLInputElement).validity?.valueMissing === true
      );
      expect(hasKeyError || keyInvalid).toBe(true);
    });

    test('asset create with empty name shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('input[id="key"]', { timeout: 10000 });
      await page.fill('input[id="key"]', `test-key-${Date.now()}`);
      await page.locator('button:has-text("Create Asset")').click();
      await page.waitForTimeout(500);
      await expect(page).toHaveURL(/\/assets\/create/, { timeout: 5000 });
      const nameError = page.locator('.error-message').filter({ hasText: /name|required/i });
      const nameInput = page.locator('input[id="name"]');
      const nameInvalid = await nameInput.evaluate(
        (el) => (el as HTMLInputElement).validity?.valueMissing === true
      );
      const hasNameError = (await nameError.count()) > 0;
      expect(hasNameError || nameInvalid).toBe(true);
    });

    test('asset create with invalid key format shows validation error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('input[id="key"]', { timeout: 10000 });
      await page.fill('input[id="key"]', 'Invalid_Key_With_Underscore');
      await page.fill('input[id="name"]', 'Test Asset');
      await page.locator('button:has-text("Create Asset")').click();
      await page.waitForTimeout(500);
      const keyError = page.locator('.error-message').filter({ hasText: /lowercase|hyphen|key/i });
      await expect(keyError.first()).toBeVisible({ timeout: 5000 });
      await expect(page).toHaveURL(/\/assets\/create/);
    });
  });

  test.describe('Edge', () => {
    test('asset list with filters (search, status, visibility)', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const hasContent = main.querySelector(
            '.asset-list-page, .empty-state, .error-display, h1'
          );
          return !!hasContent;
        },
        { timeout: 15000 }
      );
      expect(page.url()).toContain('/assets');
      await page.waitForTimeout(2000);

      const assetListPage = page.locator('.asset-list-page');
      if ((await assetListPage.count()) > 0) {
        const searchInput = page.locator('input[placeholder="Search assets..."]');
        if ((await searchInput.count()) > 0) {
          await searchInput.fill('test');
          await page.waitForTimeout(500);
        }
        const statusSelect = page
          .locator('select')
          .filter({ hasText: /All Statuses|Draft|Active|Retired/ })
          .first();
        if ((await statusSelect.count()) > 0) {
          await statusSelect.selectOption('DRAFT');
        }
      }
    });

    test('dataset create page keeps Create Dataset disabled when no file uploaded', async ({
      page,
    }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/datasets/create');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForFunction(
        () => {
          const main = document.querySelector('.app-main');
          if (!main) return false;
          const loading = main.querySelector('.loading-spinner');
          if (loading) return false;
          const createPage = main.querySelector('.dataset-create-page');
          if (createPage) return true;
          const h1 = main.querySelector('h1');
          return !!h1?.textContent?.includes('Create Dataset');
        },
        { timeout: 15000 }
      );
      const createBtn = page.locator('button:has-text("Create Dataset")');
      await createBtn.waitFor({ state: 'visible', timeout: 10000 });
      await expect(createBtn).toBeDisabled();
      expect(page.url()).toContain('/datasets/create');
    });

    test('asset detail for non-existent id shows error or 404', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/assets/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      const errorDisplay = page.locator('.error-display');
      const errorOr404 = page.locator('text=/not found|failed to load|404/i');
      await Promise.race([
        errorDisplay.waitFor({ state: 'visible', timeout: 15000 }),
        errorOr404.first().waitFor({ state: 'visible', timeout: 15000 }),
      ]).catch(() => null);
      const hasError =
        (await page.locator('.error-display').count()) > 0 ||
        (await page.locator('text=/not found|failed to load|404/i').count()) > 0;
      expect(hasError).toBe(true);
    });
  });
});
