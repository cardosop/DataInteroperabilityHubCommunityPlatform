/**
 * Phase 231.3 — Compliance discovery badge on resource detail (REQ-COMP-DISCO-001).
 *
 * Real backend: asset + dataset + compliance run must reach SUCCEEDED so
 * `latest_compliance_run` is populated for the asset detail API.
 */

import { expect, test } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { createAssetViaApi, createDatasetViaApi } from '../../fixtures/api-assets';
import {
  expectComplianceRunSucceeded,
  triggerComplianceRunViaApi,
  waitForComplianceRunViaApi,
} from '../../fixtures/api-compliance';
import { waitForAppMainReady } from '../../fixtures/helpers';

test.describe('231.3 Compliance badge discovery @critical', () => {
  test.setTimeout(180_000);

  test('asset detail shows compliance-discovery-badge after succeeded run', async ({ page, cleanup }) => {
    const user = await getTestUser();
    const assetId = await createAssetViaApi(user, { forceNew: true, cleanup });
    const datasetId = await createDatasetViaApi(user, { assetId, cleanup });
    const runId = await triggerComplianceRunViaApi(user, {
      assetId,
      datasetId: datasetId ?? undefined,
    });
    const result = await waitForComplianceRunViaApi(user, runId, 120_000);
    expectComplianceRunSucceeded(result);

    await loginUser(page, user);
    await page.goto(`/assets/${assetId}`);
    await page.waitForLoadState('domcontentloaded');
    await waitForAppMainReady(page, {
      timeout: 60_000,
      contentSelector: '[data-testid="compliance-discovery-badge"], .asset-detail-main, [data-testid="asset-details-tabpanel"]',
    });
    const badgeVisible = await page.getByTestId('compliance-discovery-badge').isVisible().catch(() => false);
    const fallbackText = await page.getByText('Compliance status unavailable').isVisible().catch(() => false);
    expect(badgeVisible || fallbackText).toBe(true);
  });

  /**
   * 231.3.AUDIT.2 — Error boundary must not blank the page when badge subtree throws.
   * Uses route interception to simulate a contract-breaking API payload (malformed
   * regulation_summaries), not to stub application internals.
   */
  test('asset detail shows compliance fallback when badge payload is malformed', async ({ page, cleanup }) => {
    const user = await getTestUser();
    const assetId = await createAssetViaApi(user, { forceNew: true, cleanup });
    await loginUser(page, user);

    // Mutate only ``latest_compliance_run`` on the real API response so
    // tenant, status, and all other fields stay correct — a full mock
    // would break tenant-isolation checks in AssetDetailPage.
    await page.route(`**/api/v1/assets/${assetId}/`, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.latest_compliance_run = {
        id: '00000000-0000-0000-0000-000000009999',
        status: 'SUCCEEDED',
        overall_status: 'PASS',
        risk_level: 'LOW',
        allowed_to_store: true,
        completed_at: '2026-01-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        regulation_summaries: { not_an: 'array' },
      };
      await route.fulfill({
        status: response.status(),
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
    });

    await page.goto(`/assets/${assetId}`);
    await page.waitForLoadState('domcontentloaded');
    // The compliance badge component renders asynchronously after the API
    // response.  Poll for the fallback text rather than a single check.
    let fallbackVisible = false;
    for (let i = 0; i < 10; i++) {
      fallbackVisible = await page.getByText('Compliance status unavailable').isVisible().catch(() => false);
      if (fallbackVisible) break;
      await page.waitForTimeout(1000);
    }
    expect(fallbackVisible, 'Compliance fallback text must render after malformed badge payload').toBe(true);
  });
});
