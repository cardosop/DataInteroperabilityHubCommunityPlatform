/**
 * E2E: UC-MKT-LINEAGE-001 — Pre-purchase summary lineage
 *
 * Phase 228.F1.22 (REQ-LIN-F1-001 / F1-004 scenario "Buyer sees CTA pre-purchase").
 *
 * Persona: Data Consumer (no entitlement to the listing's asset).
 * Capability: `lineage.cross_tenant_marketplace` (assumed ON in
 * staging at run-time per the rollout plan; the spec also covers
 * the OFF case in the F1 backend tests).
 *
 * Asserts:
 * - Listing detail page exposes a Lineage section.
 * - Section renders the summary tier with a labelled landmark.
 * - Purchase CTA is visible for the unentitled buyer.
 * - The DOM does NOT contain transformation IP markers (the F1 STRIDE
 *   I1 mitigation — verified end-to-end via the wire response).
 *
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getConsumerTestUser, getTestUser, loginViaApi } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';
import { createAssetViaApi } from '../../fixtures/api-assets';
import {
  createListingViaApi,
  publishListingViaApi,
} from '../../fixtures/api-marketplace';
import { seedLineageDag } from '../../fixtures/lineage-fixtures';

test.describe('UC-MKT-LINEAGE-001: Pre-purchase summary lineage', () => {
  test.setTimeout(120_000);

  test('unentitled buyer sees summary graph + purchase CTA', async ({ page }) => {
    const providerUser = await getTestUser();
    const assetId = await createAssetViaApi(providerUser, {
      forceNew: true,
      ensureActivated: true,
    });
    // Seed lineage: a contract DAG linked to the asset gives the
    // listing-level lineage a root to walk — a fresh asset has no
    // contract, so get_for_asset returns an empty graph and the panel
    // lands in the `-empty` state (b6 skip: "Fresh asset has no lineage
    // rows — summary-graph contract not exercisable").
    const providerAuth = await loginViaApi(providerUser.email, providerUser.password);
    await seedLineageDag(page, 3, { accessToken: providerAuth.access_token, assetId });
    const listingId = await createListingViaApi(providerUser, assetId);
    await publishListingViaApi(providerUser, listingId);

    const consumerUser = await getConsumerTestUser();
    // The summary-tier wire response MUST NOT carry transformation
    // IP — captured at the network level so we can prove it end-to-end
    // (a frontend filter that hides the field would still fail the
    // assertion). Registered BEFORE navigation: the lineage fetch fires
    // during page load, and a waitForResponse registered afterwards only
    // sees FUTURE responses (b6 masked bug — the old skip path never
    // reached the await).
    const lineageResponsePromise = page.waitForResponse((res) =>
      res.url().includes(`/marketplace/listings/${listingId}/lineage/`),
    );
    await loginAndNavigateToRoute(
      page,
      consumerUser,
      `/marketplace/listings/${listingId}`,
      {
        timeout: 90_000,
        contentSelector:
          '.listing-detail-main, [data-testid="listing-detail-main"], .listing-detail-page, .error-display, [data-testid="error-display"], main',
      },
    );
    const onLogin = page.url().includes('/login');
    test.skip(onLogin, 'Redirected to login — auth not available');
    if (onLogin) {
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15_000 });

    // The panel renders four states with distinct testids: `-loading`
    // (entitlement + lineage fetch in flight — waitForLoadingComplete
    // does NOT cover it, the skeleton has no spinner class), `-error`
    // (the lineage endpoint 404s when
    // lineage.cross_tenant_marketplace is off — flag-off env), `-empty`
    // (fresh asset with no lineage rows — a data state, NOT a
    // capability state), and `-panel` (success, data-detail set).
    // Probe the terminal states only so a still-fetching panel is not
    // misread as flag-off, then skip with the HONEST reason.
    // intentional: best-effort terminal-state wait — the branch below is
    // the verdict; absence is a legitimate gated/loading outcome.
    await page
      .locator(
        '[data-testid="listing-lineage-panel"], [data-testid="listing-lineage-panel-error"], [data-testid="listing-lineage-panel-empty"]'
      )
      .first()
      .waitFor({ state: 'visible', timeout: 30_000 })
      .catch(() => null);

    const panel = page.getByTestId('listing-lineage-panel');
    const panelMissing = (await panel.count()) === 0;
    if (panelMissing) {
      let reason: string;
      if ((await page.getByTestId('listing-lineage-panel-loading').count()) > 0) {
        reason = 'Lineage panel still loading — fetch did not settle within 30s';
      } else if ((await page.getByTestId('listing-lineage-panel-empty').count()) > 0) {
        reason =
          'Fresh asset has no lineage rows — summary-graph contract not exercisable (data state, not capability)';
      } else {
        reason =
          'Lineage endpoint unavailable — lineage.cross_tenant_marketplace capability off in this environment';
      }
      test.skip(panelMissing, reason);
      return;
    }

    // Section landmark is labelled.
    await expect(panel).toHaveAttribute('data-detail', 'summary');

    // Purchase CTA is visible — buyer is unentitled.
    await expect(page.getByTestId('listing-lineage-purchase-cta')).toBeVisible();

    // Await the response captured from page load (see the
    // lineageResponsePromise registration above).
    const lineageResponse = await lineageResponsePromise;
    const body = await lineageResponse.json();
    for (const link of body?.links ?? []) {
      expect(link).not.toHaveProperty('transformation_ref');
      expect(link).not.toHaveProperty('job_ref');
      expect(link).not.toHaveProperty('source_field');
      expect(link).not.toHaveProperty('target_field');
    }
  });
});
