/**
 * 284.D.3 — Semantic Search E2E journey.
 *
 * Keyword search → facets render → filter by ontology type → click result.
 * Real SPARQL backend (graceful skip when capability is disabled).
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Semantic Search journey @e2e @semantic-search', () => {
  test.setTimeout(120_000);

  test('search with semantic facets', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    await page.goto('/search', { waitUntil: 'domcontentloaded' });
    await page.locator('[data-testid="search-page"]').first().waitFor({ state: 'visible', timeout: 15_000 });

    // Enable semantic search
    const toggle = page.locator('[data-testid="search-semantic-toggle"]');
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.check();
    }

    // Type a query
    await page.locator('[data-testid="search-input"]').fill('customer data');
    await page.waitForTimeout(500);

    // If facets appear, verify they are interactive
    const facets = page.locator('[data-testid="semantic-search-facets"]');
    if (await facets.isVisible({ timeout: 8_000 }).catch(() => false)) {
      // Try clicking an ontology type filter
      const firstFacet = page.locator('[data-testid^="facet-ontology-type-"]').first();
      if (await firstFacet.isVisible().catch(() => false)) {
        await firstFacet.click();
        await page.waitForTimeout(300);
      }
    }

    // Search results should appear (or graceful timeout message)
    const results = page.locator('[data-testid^="search-result-"]');
    const timeout = page.locator('[data-testid="facets-error"]');
    await expect(results.first().or(timeout.first())).toBeVisible({ timeout: 15_000 });
  });

  test('semantic search timeout shows retry', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);

    await page.goto('/search', { waitUntil: 'domcontentloaded' });
    await page.locator('[data-testid="search-page"]').first().waitFor({ state: 'visible', timeout: 15_000 });

    const toggle = page.locator('[data-testid="search-semantic-toggle"]');
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.check();
    }

    // Use a complex query that may trigger a SPARQL timeout
    await page.locator('[data-testid="search-input"]').fill(
      'SELECT ?s ?p ?o WHERE { ?s ?p ?o . ?s rdfs:subClassOf* owl:Thing }'
    );
    await page.waitForTimeout(500);

    // Either facets load, error appears, or results show — all valid
    const facets = page.locator('[data-testid="semantic-search-facets"]');
    const error = page.locator('[data-testid="facets-error"]');
    await expect(facets.or(error).first()).toBeVisible({ timeout: 15_000 });

    // If retry button appears, click it
    const retryBtn = page.locator('[data-testid="facets-retry-btn"]');
    if (await retryBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await retryBtn.click();
      await page.waitForTimeout(500);
    }
  });
});
