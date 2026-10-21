/**
 * E2E — Asset detail page IRI discovery (Phase 230.1.7 / REQ-SEM-DISCO-002).
 *
 * Closes the B5 dual-channel adoption gap from Phase 226: this is
 * the FIRST spec in the suite that exercises the
 * `verifySemanticIri()` helper as a real assertion.  The helper
 * runs the 5-step semantic-IRI verification (303 dereference,
 * JSON-LD shape, RDF type, SPARQL triple presence, negative-path
 * 404 on bogus UUID) against the freshly-created asset.
 *
 * The UI assertion confirms the canonical IRI surfaces in the
 * `<CanonicalIriCard>` per REQ-SEM-DISCO-001 — the visual contract
 * the engineering team committed to alongside the API-level
 * dual-channel guard.
 */
import { AxeBuilder } from '@axe-core/playwright';

import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { createAssetViaApi } from '../../fixtures/api-assets';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';
import { verifySemanticIri } from '../../fixtures/verifySemantic';
import { expectNoSeriousViolations } from '../../fixtures/axeAudit';


test.describe('Asset detail — canonical IRI surfacing + dual-channel verification', () => {
  test('CanonicalIriCard renders + verifySemanticIri passes', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    const assetId = await createAssetViaApi(user);

    // Navigate to the asset detail page + assert the card renders.
    await loginAndNavigateToRoute(page, `/assets/${assetId}`, user);
    const card = page.getByTestId('canonical-iri-card');
    await expect(card).toBeVisible();

    // The IRI value appears verbatim (REQ-SEM-DISCO-001 scenario
    // "Card renders on Asset detail" — the canonical IRI is in
    // monospace).
    const iriValue = page.getByTestId('canonical-iri-value');
    await expect(iriValue).toBeVisible();
    const iriText = (await iriValue.textContent()) ?? '';
    expect(iriText).toMatch(/\/id\/asset\//);

    // Open-in-SPARQL link encodes the IRI inside DESCRIBE per the
    // spec scenario "Open in SPARQL link encodes IRI".
    const sparqlLink = page.getByTestId('canonical-iri-open-sparql');
    const href = await sparqlLink.getAttribute('href');
    expect(href).toContain('/semantic?tab=sparql&query=DESCRIBE%20%3C');
    expect(href).toContain(encodeURIComponent(iriText.trim()));

    // ---- B5 dual-channel adoption — verifySemanticIri 5-step helper.
    // This is the first spec in the suite that calls the helper for
    // real (Phase 226's adoption gap closes here).
    await verifySemanticIri(page, 'asset', assetId);

    // 230.1.8 — axe-audit the canonical IRI card scope. Asset detail
    // is a per-test-id route (not in the static ROUTES_TO_AUDIT list
    // at frontend/e2e/a11y/axe-detail-pages.spec.ts), so the audit
    // for the new card surface lives inline with the journey spec
    // that creates the asset.
    const results = await new AxeBuilder({ page })
      .include('[data-testid="canonical-iri-card"]')
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    expectNoSeriousViolations({
      violations: results.violations,
      passes: results.passes ?? [],
      incomplete: results.incomplete ?? [],
      inapplicable: results.inapplicable ?? [],
    });
  });

  test('Card hidden when canonical_iri is absent (negative path)', async ({ page }) => {
    // Negative-path doc: when the API returns a payload without
    // `canonical_iri`, the card MUST be absent — not a placeholder
    // box, not a "loading" skeleton. Per REQ-SEM-DISCO-001 scenario
    // "Null IRI hides the card".
    //
    // Since real assets emit canonical_iri unconditionally (the
    // serializer at hub/apps/assets/serializers.py:33 always
    // produces a value), this test relies on a route mock that
    // strips the field. The mock targets ONE detail-route call
    // and lets every other request pass through untouched.
    const user = await getTestUser();
    await loginUser(page, user);
    const assetId = await createAssetViaApi(user);

    await page.route(`**/api/v1/assets/${assetId}/`, async (route) => {
      const original = await route.fetch();
      const body = await original.json();
      delete body.canonical_iri;
      await route.fulfill({
        status: original.status(),
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
    });

    await loginAndNavigateToRoute(page, `/assets/${assetId}`, user);
    // The page mounts (the asset name is visible) but the card is
    // not in the DOM at all.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByTestId('canonical-iri-card')).not.toBeVisible();
  });
});
