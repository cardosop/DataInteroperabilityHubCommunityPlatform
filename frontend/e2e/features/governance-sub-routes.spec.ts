/**
 * close-test-coverage-gaps 4.4 — governance sub-route coverage.
 *
 * Walks the compliance surfaces under /governance the component-level
 * coverage never exercised live:
 *   1. /governance/consent/purposes      — purpose CRUD (create via UI)
 *   2. /governance/consent/dashboard     — per-purpose aggregate posture
 *   3. /governance/retention/dashboard   — enforcement snapshot
 *   4. /governance/dsar-requests(+:id)   — handler queue → detail
 *   5. /governance/dpia/:id/review       — DPO decision (PLATFORM_ADMIN)
 *   6. /governance/breach/templates      — tenant override upsert
 *   7. /governance/breach/:id            — seeded incident + transition
 *   8. /governance/processor-agreements  — add processor via UI
 *   9. strict role-gate negative         — DATA_PROVIDER denied
 *
 * Conventions (1.3/1.4/4.1 contracts): real-flow-first, every skip
 * CONDITIONAL (no test.skip(true)), role gates asserted STRICTLY —
 * TENANT_ADMIN/PLATFORM_ADMIN provably carry the admission roles and
 * the 1.1/4.4 seeder contract (e2e_flag_defaults) keeps the compliance
 * capability flags ON for E2E tenants, so a /403 or /unavailable
 * landing is a REAL regression and fails the run. Seeds go through the
 * real wire API (fixtures/api-governance.ts) — no mocks, no
 * page.evaluate data fabrication.
 */

import { expect, test } from '@playwright/test';

import {
  createBreachIncidentViaApi,
  createConsentPurposeViaApi,
  createDpiaInReviewViaApi,
  createDsarRequestViaApi,
} from '../fixtures/api-governance';
import {
  getPlatformAdminUser,
  getTenantAdminUser,
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import { environmentSkipGuard } from '../fixtures/envPolicy.cjs';
import {
  loginAndNavigateToRoute,
  waitForRoleGuardResolved,
} from '../fixtures/helpers';

const run = Date.now();

/** Guard the shared post-nav conventions: a login redirect is an
 *  environment failure (W16 — skip), while /403 or /unavailable is a
 *  REAL regression for the personas this spec admits. */
function assertAdmitted(page: import('@playwright/test').Page, route: string): void {
  const url = page.url();
  if (url.includes('/login')) {
    environmentSkipGuard(`Redirected to login navigating to ${route} — auth may have expired`);
    test.skip(url.includes('/login'), `Redirected to login navigating to ${route} — auth may have expired`);
  }
  expect(
    !url.includes('/403') && !url.includes('/unavailable') && !url.includes('/coming-soon'),
    `${route} bounced to ${url} — role/capability gate regression for the admitted persona`
  ).toBe(true);
}

test.describe('Feature: Governance sub-routes (4.4)', () => {
  test.setTimeout(120000);

  test('consent purposes page renders and creates a purpose through the real flow', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/consent/purposes', {
      timeout: 90000,
      contentSelector: '.governance-consent-purposes, .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/consent/purposes');

    await expect(page.locator('.governance-consent-purposes')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Consent purposes', exact: true })).toBeVisible();

    // The create flow drives two window.prompt dialogs (key, then
    // display name) — answer them with a unique key so the write is
    // real and never collides with the per-tenant unique constraint.
    // The key is a SlugField on the wire (letters/digits/_/- only) —
    // dots 400 VALIDATION_ERROR.
    const purposeKey = `e2e-purpose-${run}`;
    page.on('dialog', async (dialog) => {
      if (dialog.type() === 'prompt') {
        if (dialog.defaultValue().includes('marketing.email')) {
          await dialog.accept(purposeKey);
        } else {
          await dialog.accept('E2E Purpose');
        }
      } else {
        await dialog.dismiss();
      }
    });
    await page.getByRole('button', { name: 'Add purpose' }).click();

    await expect
      .poll(
        async () => (await page.locator('.governance-consent-purposes li', { hasText: purposeKey }).count()),
        { timeout: 15000 }
      )
      .toBeGreaterThan(0);
    await expect(page.locator('p[role="alert"]')).not.toBeVisible();
  });

  test('consent dashboard lists the seeded purpose', async ({ page }) => {
    const user = await getTenantAdminUser();
    const purposeKey = `e2e-purpose-${run}-dash`;
    await createConsentPurposeViaApi(user, { key: purposeKey, name: 'E2E Dashboard Purpose' });

    await loginAndNavigateToRoute(page, user, '/governance/consent/dashboard', {
      timeout: 90000,
      contentSelector: '.governance-consent-dashboard, .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/consent/dashboard');

    await expect(page.locator('.governance-consent-dashboard')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Consent dashboard', exact: true })).toBeVisible();

    // The dashboard table renders one row per purpose; the seeded
    // purpose (created via the real wire API) must appear.
    await expect(page.locator('code', { hasText: purposeKey }).first()).toBeVisible({ timeout: 15000 });
  });

  test('retention dashboard renders the enforcement snapshot', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/retention/dashboard', {
      timeout: 90000,
      contentSelector: '.governance-retention-policy-list-page, .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/retention/dashboard');

    await expect(page.locator('.governance-retention-policy-list-page')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Retention enforcement', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Quarterly audit counts' })).toBeVisible();
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('dsar queue lists the seeded request and opens its detail page', async ({ page }) => {
    const user = await getTenantAdminUser();
    const subjectEmail = `e2e-dsar-${run}@example.com`;
    await createDsarRequestViaApi(user, subjectEmail);

    await loginAndNavigateToRoute(page, user, '/governance/dsar-requests', {
      timeout: 90000,
      contentSelector: 'h1, .error-display, [data-testid="error-display"]',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/dsar-requests');

    // Real copy — the 4.4 i18n table ships governance.dsar.* English
    // keys (before it, the UI rendered the raw key string).
    await expect(page.getByRole('heading', { name: 'Data subject requests (DSAR)' })).toBeVisible({ timeout: 30000 });

    // The seeded request appears in the handler queue.
    const row = page.locator('tr', { hasText: subjectEmail }).first();
    await expect(row).toBeVisible({ timeout: 15000 });

    await row.getByRole('button', { name: 'Open' }).click();
    await page.waitForURL(/\/governance\/dsar-requests\/[0-9a-f-]+/, { timeout: 15000 });

    // Detail page: real title + the fulfilment-clock surface.
    await expect(page.getByRole('heading', { name: 'DSAR request detail' })).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('Fulfilment deadline (UTC)').first()).toBeVisible();
  });

  test('dpia review page renders and submits the decision', async ({ page }) => {
    const admin = await getTenantAdminUser();
    const dpiaTitle = `E2E DPIA Review ${run}`;
    const dpiaId = await createDpiaInReviewViaApi(admin, dpiaTitle);

    // The review action requires DPO / LEGAL_ADMIN (+ PLATFORM_ADMIN);
    // the E2E persona carrying that authority is the platform admin.
    const reviewer = await getPlatformAdminUser();
    await loginAndNavigateToRoute(page, reviewer, `/governance/dpia/${dpiaId}/review`, {
      timeout: 90000,
      contentSelector: '[data-testid="dpia-review-page"], .error-display, [data-testid="error-display"], h2',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, `/governance/dpia/${dpiaId}/review`);

    const reviewPage = page.getByTestId('dpia-review-page');
    await expect(reviewPage).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: `Review: ${dpiaTitle}` })).toBeVisible();
    // The seeded record was submitted — the decision surface renders.
    await expect(page.getByLabel('DPO summary')).toBeVisible();

    await page.getByLabel('DPO summary').fill('E2E review — approved with LOW residual risk.');
    await page.getByRole('button', { name: 'Submit decision' }).click();

    // Post-decision the page navigates to the review queue.
    await page.waitForURL(/\/governance\/dpia\/review-queue/, { timeout: 15000 });
    await expect(page.getByTestId('dpia-review-queue')).toBeVisible({ timeout: 30000 });
  });

  test('breach templates page saves a tenant override', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/breach/templates', {
      timeout: 90000,
      contentSelector: 'h1, .error-display, [data-testid="error-display"]',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/breach/templates');

    await expect(page.getByRole('heading', { name: 'Breach notification templates' })).toBeVisible({ timeout: 30000 });

    // The catalog always ships platform templates (GDPR at minimum),
    // so the regime select is populated — the real upsert path runs.
    const regimeSelect = page.locator('form select').first();
    await expect(regimeSelect).toBeVisible({ timeout: 15000 });

    const subjectInput = page.locator('form input').first();
    const bodyTextarea = page.locator('form textarea').first();
    await subjectInput.fill(`E2E subject ${run}`);
    await bodyTextarea.fill('Breach of $incident_title — notification to $authority_name under $regime before $deadline_utc.');

    const upsertResponse = page.waitForResponse(
      (resp) => resp.url().includes('breach/template-overrides/upsert') && resp.request().method() === 'POST',
      { timeout: 15000 }
    );
    await page.getByRole('button', { name: 'Save tenant override' }).click();
    const upsert = await upsertResponse;
    expect(upsert.status()).toBeLessThan(500);
    expect(upsert.ok()).toBe(true);

    // A failed upsert surfaces as an ErrorDisplay; the save must stay clean.
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('breach detail page renders the seeded incident and transitions status', async ({ page }) => {
    const user = await getTenantAdminUser();
    const incidentTitle = `E2E Breach ${run}`;
    const incidentId = await createBreachIncidentViaApi(user, incidentTitle);

    await loginAndNavigateToRoute(page, user, `/governance/breach/${incidentId}`, {
      timeout: 90000,
      contentSelector: 'h1, .error-display, [data-testid="error-display"]',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, `/governance/breach/${incidentId}`);

    // The incident title renders as the page heading.
    await expect(page.getByRole('heading', { name: incidentTitle })).toBeVisible({ timeout: 30000 });
    // The meta line renders as "Status: <value> · Supervisory deadline: …".
    await expect(page.getByText('Status:').first()).toBeVisible();

    // Real transition: OPEN → CONTAINED through the PATCH status action.
    await page.getByRole('button', { name: 'Mark contained' }).click();
    await expect
      .poll(async () => (await page.getByText('CONTAINED', { exact: true }).count()), {
        timeout: 15000,
      })
      .toBeGreaterThan(0);
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('processor agreements page adds a processor through the real flow', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/processor-agreements', {
      timeout: 90000,
      contentSelector: '.governance-processor-agreements, .error-display, [data-testid="error-display"], h1',
      acceptRedirectToLogin: false,
    });
    assertAdmitted(page, '/governance/processor-agreements');

    await expect(page.locator('.governance-processor-agreements')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Processor agreements' })).toBeVisible();

    const processorName = `E2E Processor ${run}`;
    await page.getByLabel('Name', { exact: true }).fill(processorName);
    await page.getByRole('button', { name: 'Save', exact: true }).click();

    // The created processor appears in the processors list.
    await expect
      .poll(async () => (await page.locator('ul li', { hasText: processorName }).count()), {
        timeout: 15000,
      })
      .toBeGreaterThan(0);
    await expect(page.locator('p[role="alert"]').first()).not.toBeVisible();
  });

  test('data-provider persona is denied the consent surface (strict role gate)', async ({ page }) => {
    // The DATA_PROVIDER persona carries no governance admission role —
    // the parent ProtectedRoute must bounce to /403.
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/governance/consent/purposes', { waitUntil: 'domcontentloaded' });

    const resolved = await waitForRoleGuardResolved(page, {
      forbiddenPathPrefix: '/governance',
      timeout: 30000,
    });
    if (resolved.includes('/login')) {
      environmentSkipGuard('DATA_PROVIDER role-gate negative: redirected to login — auth may have expired');
      test.skip(resolved.includes('/login'), 'Redirected to login — auth may have expired');
    }
    expect(resolved.includes('/403'), `expected /403 for DATA_PROVIDER, got ${resolved}`).toBe(true);
  });
});
