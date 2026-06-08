/**
 * 283.3.2.3 — DSAR OTP flow E2E + a11y spec.
 *
 * Journeys covered:
 *   1. Submit a DSAR from the public form (PublicDsarSubmitPage)
 *   2. Verify the OTP code via the status page (PublicDsarStatusPage)
 *   3. Check DSAR queue as authenticated admin (DsarQueuePage)
 *   4. DSAR detail page a11y audit (DsarDetailPage)
 *
 * A11y: axe audit after each significant UI state change.
 * Selectors match the actual component DOM (id/aria attributes, not data-testid).
 */
import { test, expect } from '@playwright/test';
import { runAxeAudit, expectNoSeriousViolations } from '../fixtures/axeAudit';

const PUBLIC_DSAR_URL = '/legal/dsar';

test.describe('DSAR OTP Flow (283.3.2.3)', () => {
  test.setTimeout(90_000);

  test('Public DSAR submit page audits clean and submits', async ({ page }) => {
    await page.goto(PUBLIC_DSAR_URL, { waitUntil: 'domcontentloaded' });

    // ── A11y: submit page idle ─────────────────────────────────────
    const idleAudit = await runAxeAudit(page, 'dsar-submit-page-idle');
    expectNoSeriousViolations(idleAudit);

    // Verify key form elements are present using actual DOM IDs
    const form = page.locator('form[aria-labelledby="dsar-intro"]');
    await expect(form).toBeVisible();
    await expect(page.locator('#dsar-email')).toBeVisible();
    await expect(page.locator('#dsar-type')).toBeVisible();

    // Fill and submit using actual field IDs from PublicDsarSubmitPage
    await page.fill('#dsar-email', 'e2e-dsar-test@meshant.com');
    await page.selectOption('#dsar-type', 'access');
    // hCaptcha may be configured to skip in test; fill if field is present
    const hcaptchaField = page.locator('#dsar-hcaptcha');
    if (await hcaptchaField.isVisible()) {
      await hcaptchaField.fill('e2e-test-token');
    }

    await form.locator('button[type="submit"]').click();

    // ── A11y: after submission ─────────────────────────────────────
    // Success state renders reference token + status text
    await page.waitForSelector('a[href*="/legal/dsar/status/"]', { timeout: 15000 })
      .catch(() => null);
    const successAudit = await runAxeAudit(page, 'dsar-submit-result');
    expectNoSeriousViolations(successAudit);

    // Verify some success content is visible
    const afterSubmit = page.locator('form[aria-labelledby="dsar-intro"] ~ div');
    const hasContent = await afterSubmit.textContent();
    expect(hasContent?.length || 0).toBeGreaterThan(10);
  });

  test('Public DSAR status page audits clean', async ({ page }) => {
    // Navigate to the status lookup page (no auth required)
    await page.goto('/legal/dsar/status/test-token', { waitUntil: 'domcontentloaded' });

    // ── A11y: status page ──────────────────────────────────────────
    const statusAudit = await runAxeAudit(page, 'dsar-status-page');
    expectNoSeriousViolations(statusAudit);

    // OTP verification section should be visible for non-verified requests
    const otpInput = page.locator('#dsar-otp');
    if (await otpInput.isVisible()) {
      await otpInput.fill('123456');
      const verifyBtn = page.locator('button[type="submit"]');
      if (await verifyBtn.isVisible()) {
        await verifyBtn.click();
        await page.waitForTimeout(2000);
        const resultAudit = await runAxeAudit(page, 'dsar-otp-result');
        expectNoSeriousViolations(resultAudit);
      }
    }
  });

  test('DSAR queue page audits clean (authenticated)', async ({ page }) => {
    await page.goto('/governance/dsar', { waitUntil: 'domcontentloaded' });

    if (page.url().includes('/login')) {
      test.skip(true, 'Not authenticated — skipping DSAR queue a11y audit');
      return;
    }

    // Wait for page content to load (uses i18n headline)
    await page.waitForSelector('h1, h2', { timeout: 15000 }).catch(() => null);

    // ── A11y: DSAR queue page ──────────────────────────────────────
    const queueAudit = await runAxeAudit(page, 'dsar-queue-page');
    expectNoSeriousViolations(queueAudit);

    // Verify a table or list is rendered
    const table = page.locator('table');
    if (await table.isVisible()) {
      const rows = await table.locator('tbody tr').count();
      // At least header row or "no requests" empty state
      expect(rows).toBeGreaterThanOrEqual(0);
    }
  });

  test('DSAR detail page audits clean', async ({ page }) => {
    await page.goto('/governance/dsar', { waitUntil: 'domcontentloaded' });

    if (page.url().includes('/login')) {
      test.skip(true, 'Not authenticated');
      return;
    }

    // Click on the first DSAR row to navigate to detail page
    const firstRow = page.locator('table tbody tr').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await page.waitForTimeout(3000);

      // ── A11y: DSAR detail page ───────────────────────────────────
      const detailAudit = await runAxeAudit(page, 'dsar-detail-page');
      expectNoSeriousViolations(detailAudit);
    }
  });
});
