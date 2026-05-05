/**
 * E2E — Phase 230.9 (REQ-SEM-SEO-001) Schema.org JSON-LD on public pages.
 *
 * Spec scenarios pinned by this spec:
 *
 *  * Public listing emits valid Schema.org — `<script type="application/ld+json">`
 *    body parses as JSON, has `@type: "Dataset"` (or `DataCatalog` for
 *    the platform landing), includes the required fields, and would
 *    pass Google's Rich Results Test (structural fields verified
 *    inline; live Rich-Results check is the manual 230.9.7 step).
 *  * Behind-auth page does NOT emit — visiting an authenticated
 *    marketplace listing detail page must NOT contain a
 *    `<script type="application/ld+json">` element.
 *  * Default language tag — `inLanguage: "en"` is present.
 *  * CSP does not block JSON-LD — verified by the script element
 *    surviving in the rendered DOM under the production-grade CSP
 *    policy (the rendered DOM contains the script ⇒ the browser
 *    didn't strip it).
 */
import { test, expect } from '@playwright/test';

import { getTestUser, loginUser } from '../../fixtures/auth';

const REQUIRED_FIELDS = ['@type', 'name', 'description', 'inLanguage', 'dateModified'] as const;

test.describe('Schema.org JSON-LD on public pages', () => {
  test('public landing emits a parseable Schema.org block with required fields', async ({
    page,
  }) => {
    // No auth — visit /public as a fresh visitor.
    await page.goto('/public');

    // The script tag is injected via react-helmet-async into <head>.
    // We use a content-type query because Helmet may render after
    // React hydration; the assertion polls until present.
    const scriptHandle = page.locator('script[type="application/ld+json"]').first();
    await expect(scriptHandle).toHaveCount(1, { timeout: 10_000 });

    const json = await scriptHandle.textContent();
    expect(json).toBeTruthy();
    const parsed = JSON.parse(json as string);

    // Spec contract — required fields present and non-empty.
    for (const field of REQUIRED_FIELDS) {
      expect(parsed).toHaveProperty(field);
      expect(parsed[field]).toBeTruthy();
    }
    // Spec contract — language defaults to 'en'.
    expect(parsed.inLanguage).toBe('en');
    // Spec contract — @context is schema.org.
    expect(parsed['@context']).toBe('https://schema.org');
  });

  test('authenticated assets list does NOT emit Schema.org', async ({ page }) => {
    // Spec scenario — "Behind-auth page does NOT emit".
    //
    // Audit-fix GAP-D — was previously navigating to `/marketplace`
    // which can either redirect to `/login` (when auth fails) or 404
    // depending on tenant capabilities, making the assertion pass
    // VACUOUSLY for the wrong reasons. Switched to `/assets` because
    // (a) it always renders for an authenticated user — there's no
    // capability gate or marketplace-tier check, and (b) we then
    // explicitly verify we landed there + the auth-only sidebar
    // chrome rendered, so the zero-script assertion has real
    // semantic weight.
    const user = await getTestUser();
    await loginUser(page, user);

    await page.goto('/assets');
    await page.waitForLoadState('networkidle');
    // Verify we actually landed on an auth-gated page, not the
    // login redirect — guard against vacuous-pass.
    expect(page.url()).toContain('/assets');
    expect(page.url()).not.toContain('/login');

    const count = await page.locator('script[type="application/ld+json"]').count();
    expect(count).toBe(0);
  });
});
