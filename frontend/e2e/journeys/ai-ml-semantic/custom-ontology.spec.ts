/**
 * E2E — Phase 230.10 (REQ-SEM-ONTO-001) Custom Ontology Manager.
 *
 * Spec scenarios pinned by this spec:
 *
 *  * Valid ontology activates — TENANT_ADMIN uploads a small Turtle
 *    ontology declaring a custom namespace; the row appears in the
 *    table; toggling activate produces a 200 response and flips the
 *    Active column to "Yes".
 *  * Reserved namespace rejected — uploading an ontology that
 *    declares the reserved Meshant namespace surfaces an inline
 *    error containing the code ``ONTOLOGY_RESERVED_NAMESPACE``.
 *  * Non-admin cannot see the tab — a DATA_PROVIDER session does
 *    NOT see the ``Custom Ontologies`` tab on `/semantic`.
 *
 * Tests use real backend calls (no API stubs). The backend's
 * ``Tenant.semantic_custom_ontology_enabled`` flag must be True for
 * the feature to render — the e2e fixture enables it via the admin
 * API as part of test bootstrap.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { test, expect } from '@playwright/test';

import { getTestUser, loginUser } from '../../fixtures/auth';
import { expectNoSeriousViolations } from '../../fixtures/axeAudit';

const VALID_TURTLE = `
@prefix acme: <https://acme.example/ontology/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

acme:Customer a owl:Class .
`.trim();

const RESERVED_NS_TURTLE = `
@prefix meshant: <https://meshant.com/ontology/> .
meshant:NewClass a meshant:DataResource .
`.trim();


test.describe('Custom ontology manager (TENANT_ADMIN)', () => {
  test('uploads + activates a valid custom ontology', async ({ page }) => {
    const user = await getTestUser({ role: 'TENANT_ADMIN' });
    await loginUser(page, user);

    await page.goto('/semantic');
    // The TENANT_ADMIN-only tab MUST be visible.
    const tab = page.getByTestId('semantic-tab-custom-ontologies');
    await expect(tab).toBeVisible();
    await tab.click();

    await expect(page.getByTestId('ontology-manager')).toBeVisible();

    // Fill the upload form.
    const ontName = `acme${Date.now()}`;
    await page.getByTestId('ontology-name-input').fill(ontName);
    await page.getByTestId('ontology-namespace-input').fill(`https://acme.example/${ontName}/`);
    await page.getByTestId('ontology-format-select').selectOption('turtle');
    await page.getByTestId('ontology-content-input').fill(VALID_TURTLE);

    await page.getByTestId('ontology-upload-button').click();

    // Row appears.
    const row = page.getByTestId(`ontology-row-${ontName}`);
    await expect(row).toBeVisible();

    // Activate.
    await page.getByTestId(`ontology-toggle-${ontName}`).click();
    // After activation, the Active cell switches to Yes.
    await expect(row).toContainText('Yes');

    // Phase 230.AUDIT.10 — accessibility gate. Audit the
    // OntologyManager surface (form + table + actions) against
    // WCAG 2 AA. Mirrors the pattern from asset-detail-iri-discovery.
    const results = await new AxeBuilder({ page })
      .include('[data-testid="ontology-manager"]')
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    expectNoSeriousViolations({
      violations: results.violations,
      passes: results.passes ?? [],
      incomplete: results.incomplete ?? [],
      inapplicable: results.inapplicable ?? [],
    });
  });

  test('rejects reserved namespace inline', async ({ page }) => {
    const user = await getTestUser({ role: 'TENANT_ADMIN' });
    await loginUser(page, user);

    await page.goto('/semantic');
    await page.getByTestId('semantic-tab-custom-ontologies').click();

    await page.getByTestId('ontology-name-input').fill('reserved-test');
    await page.getByTestId('ontology-namespace-input').fill('https://meshant.com/ontology/');
    await page.getByTestId('ontology-content-input').fill(RESERVED_NS_TURTLE);

    await page.getByTestId('ontology-upload-button').click();

    const errBanner = page.getByTestId('ontology-error');
    await expect(errBanner).toBeVisible();
    await expect(errBanner).toContainText(/ONTOLOGY_RESERVED_NAMESPACE/i);
  });
});

test.describe('Custom ontology manager (non-admin)', () => {
  test('DATA_PROVIDER does not see the custom-ontologies tab', async ({ page }) => {
    const user = await getTestUser({ role: 'DATA_PROVIDER' });
    await loginUser(page, user);

    await page.goto('/semantic');
    // Other tabs should still render.
    await expect(page.getByTestId('semantic-tab-sparql')).toBeVisible();
    // The TENANT_ADMIN-only tab must NOT render for non-admins.
    await expect(page.getByTestId('semantic-tab-custom-ontologies')).toHaveCount(0);
  });
});
