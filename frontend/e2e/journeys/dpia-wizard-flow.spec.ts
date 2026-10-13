/**
 * 284.F.5 — DPIA wizard flow E2E spec.
 *
 * Journeys covered:
 *   1. DPIA create — new DPIA via wizard, fill Basics step, advance to
 *      Processing, Risks & Measures, Review, and submit.
 *   2. DPIA review — the reviewer approves the submitted DPIA.
 *   3. DPIA wizard page renders without white-screen.
 *
 * close-test-coverage-gaps 4.4 rewrite: the original draft logged in via
 * the API only (no browser session), navigated as an unauthenticated
 * DATA_PROVIDER, and leaned on `.catch(() => false)` probes that silently
 * passed on /403 + /login. With the 4.4 seeder contract (compliance_dpia
 * ON), the wizard and review surfaces render for real — the spec now runs
 * the wizard as TENANT_ADMIN (create + submit) and the review as
 * PLATFORM_ADMIN (the E2E persona holding the DPO/LEGAL_ADMIN review
 * authority), through REAL browser logins and real assertions.
 *
 * Real backend only — no mocks.
 */
import { test, expect } from '../fixtures/guardedTest';
import { getPlatformAdminUser, getTenantAdminUser, loginUser } from '../fixtures/auth';

test.describe('284.F.5 — DPIA wizard flow @critical @dpia', () => {
  test.setTimeout(120_000);

  test('DPIA create — wizard steps from Basics to submit', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');

    // Navigate to the new-DPIA wizard (route param "new" = create mode).
    await page.goto('/governance/dpia/new');
    await expect(page.getByTestId('dpia-wizard')).toBeVisible({ timeout: 15_000 });

    // ── Step 0: Basics ────────────────────────────────────────────
    await page.locator('#dpia-title').fill(`E2E DPIA ${Date.now()}`);
    await page.locator('#dpia-regime').selectOption('GDPR');

    // Advance to step 1 (Processing).
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.locator('#dpia-proc')).toBeVisible({ timeout: 15_000 });

    // ── Step 1: Processing ────────────────────────────────────────
    await page
      .locator('#dpia-proc')
      .fill('E2E test processing narrative — customer analytics pipeline.');

    // Advance to step 2 (Risks & Measures).
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.locator('#dpia-risk')).toBeVisible({ timeout: 15_000 });

    // ── Step 2: Risks & Measures ──────────────────────────────────
    await page
      .locator('#dpia-risk')
      .fill('E2E test risk narrative — re-identification risk, data minimisation mitigations.');
    await page
      .locator('#dpia-mit')
      .fill('Pseudonymisation at ingest, 7-day retention for raw logs, access logged to audit.');

    // Advance to step 3 (Review).
    await page.getByRole('button', { name: /next/i }).click();

    // ── Step 3: Review → submit for review ─────────────────────────
    // dpiaService.submit() → status IN_REVIEW → redirect to the queue.
    await page.getByRole('button', { name: /submit for review/i }).click();
    await page.waitForURL(/\/governance\/dpia\/review-queue/, { timeout: 15_000 });
    await expect(page.getByTestId('dpia-review-queue')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
  });

  test('DPIA review page — reviewer approves the submitted DPIA', async ({ page }) => {
    const reviewer = await getPlatformAdminUser();
    await loginUser(page, reviewer);
    await page.waitForLoadState('domcontentloaded');

    // Navigate to the DPIA review queue.
    await page.goto('/governance/dpia/review-queue');
    await expect(page.getByTestId('dpia-review-queue')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('heading', { name: 'DPIA review queue' })).toBeVisible();

    // The wizard test above submits a DPIA into the IN_REVIEW queue —
    // click into the first pending review (rows navigate via a
    // "Review" Button, not an anchor).
    const firstReviewButton = page.getByRole('button', { name: 'Review', exact: true }).first();
    test.skip(
      (await firstReviewButton.count()) === 0,
      'No IN_REVIEW DPIA records in the queue (the wizard test seeds one — data-dependent)',
    );
    await firstReviewButton.click();
    await page.waitForLoadState('domcontentloaded');

    // The review page has outcome controls.
    await expect(page.getByTestId('dpia-review-page')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#dpia-outcome')).toBeVisible();
    await page.locator('#dpia-outcome').selectOption('APPROVED');
    await page.locator('#dpia-dpo').fill('E2E review — approved with LOW residual risk.');

    await page.getByRole('button', { name: /submit decision/i }).click();

    // Post-decision the page navigates back to the queue.
    await page.waitForURL(/\/governance\/dpia\/review-queue/, { timeout: 15_000 });
    await expect(page.getByTestId('dpia-review-queue')).toBeVisible({ timeout: 10_000 });
  });

  test('DPIA wizard page renders without white-screen', async ({ page }) => {
    const user = await getTenantAdminUser();
    await loginUser(page, user);
    await page.waitForLoadState('domcontentloaded');

    await page.goto('/governance/dpia/new');
    await page.waitForLoadState('domcontentloaded');

    // The wizard mounts with the step rail and the Basics step fields.
    await expect(page.getByTestId('dpia-wizard')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#dpia-title')).toBeVisible();
    await expect(page.locator('#dpia-regime')).toBeVisible();
  });
});
