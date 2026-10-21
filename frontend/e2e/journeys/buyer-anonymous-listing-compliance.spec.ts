/**
 * Phase 231.3.AUDIT.4 — Published marketplace listing surfaces buyer-visible compliance
 * badge without authentication.
 */

import { expect, test } from '../fixtures/test-data-cleanup';
import { getTestUser } from '../fixtures/auth';
import { createAssetViaApi, createDatasetViaApi } from '../fixtures/api-assets';
import {
  expectComplianceRunSucceeded,
  triggerComplianceRunViaApi,
  waitForComplianceRunViaApi,
} from '../fixtures/api-compliance';
import { createListingViaApi, publishListingViaApi } from '../fixtures/api-marketplace';

test.describe('231.3 Anonymous marketplace compliance badge @critical', () => {
  test.setTimeout(180_000);

  test('published listing detail shows badge without auth', async ({ browser, cleanup }) => {
    const provider = await getTestUser();
    const assetId = await createAssetViaApi(provider, { forceNew: true, cleanup });
    const datasetId = await createDatasetViaApi(provider, { assetId, cleanup });
    const runId = await triggerComplianceRunViaApi(provider, {
      assetId,
      datasetId: datasetId ?? undefined,
    });
    const result = await waitForComplianceRunViaApi(provider, runId, 120_000);
    expectComplianceRunSucceeded(result);

    const listingId = await createListingViaApi(provider, assetId, {
      title: `E2E compliance badge ${Date.now()}`,
      cleanup,
    });
    await publishListingViaApi(provider, listingId);

    const context = await browser.newContext();
    const page = await context.newPage();
    try {
      await page.goto(`/marketplace/listings/${listingId}`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('compliance-discovery-badge')).toBeVisible({ timeout: 45_000 });
    } finally {
      await context.close();
    }
  });
});
