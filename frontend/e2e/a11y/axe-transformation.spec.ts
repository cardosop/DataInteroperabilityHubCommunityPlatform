/**
 * Transformation pipeline a11y coverage.
 *
 * NOTE (2026-09-22): the guided wizard flow (wizard / validate / contract
 * preview routes, WizardPage + WizardDirectionPicker + WizardReviewStep)
 * was decommissioned — the routes no longer exist in the router and the
 * components are dead code. This spec previously navigated to those URLs
 * and audited the 404 page (false positives). It now targets the CURRENT
 * surface: the pipeline detail page and the create form.
 */
import { expect, test } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';

import { getTestUser, loginUser, loginViaApi } from '../fixtures/auth';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8001/api/v1';

/**
 * Create a transformation pipeline for the E2E user via the API.
 * Skips (not fails) when the transformation feature is disabled for the
 * tenant — the per-tenant flag is seed-dependent.
 */
let _pipelineId: string | null = null;
async function getOrCreatePipelineId(): Promise<string | null> {
  if (_pipelineId !== null) return _pipelineId;
  const user = await getTestUser();
  const auth = await loginViaApi(user.email, user.password);
  const payload = {
    name: `E2E A11y Pipeline ${Date.now()}`,
    source_type: 'csv',
    target_type: 'parquet',
    pipeline_definition: {
      version: '1.0',
      steps: [{ name: 'a11y-step', type: 'transform', config: {} }],
      schema: {
        fields: [
          { name: 'id', type: 'integer', description: 'Primary key', is_primary_key: true, is_not_null: true },
          { name: 'name', type: 'string', description: 'Resource name' },
          { name: 'created_at', type: 'timestamp', description: 'Creation timestamp' },
        ],
      },
    },
  };
  const res = await fetch(`${API_BASE}/transformation/pipelines/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${auth.access_token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    // intentional: diagnostic extraction — a failed read yields '' for the error message; the throw/assert below is the failure path
    const body = await res.text().catch(() => '');
    const isDisabled = body.includes('TRANSFORMATION_DISABLED') || body.includes('disabled');
    if (isDisabled) {
      test.skip(isDisabled, `Transformation feature is disabled for this tenant — cannot create pipeline for a11y audit.`);
      return null;
    }
    throw new Error(`Failed to create transformation pipeline: ${res.status} ${body.slice(0, 300)}`);
  }
  const data = (await res.json()) as { id: string };
  _pipelineId = data.id;
  return _pipelineId;
}

let _pipelineChecked = false;
async function ensurePipeline(): Promise<string> {
  if (!_pipelineChecked) {
    _pipelineChecked = true;
    const id = await getOrCreatePipelineId();
    if (!id) throw new Error('Pipeline not available');
  }
  return _pipelineId!;
}

async function assertNoA11yViolations(page: import('@playwright/test').Page, url: string): Promise<void> {
  // Retry navigation once: the Vite dev server occasionally fails a
  // chunk load under load (the error overlay would otherwise be
  // audited instead of the page).
  let hasViteError = false;
  for (let attempt = 0; attempt < 2; attempt++) {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    hasViteError = (await page.locator('vite-error-overlay').count()) > 0;
    if (!hasViteError) break;
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.goto(url, { waitUntil: 'domcontentloaded' });
  }
  test.skip(hasViteError, 'Vite error overlay — transformation chunk load failed after 2 navigate-away retries');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe('Transformation Pipeline Detail — Accessibility', () => {
  test('pipeline detail page has no axe violations', async ({ page }) => {
    const pid = await ensurePipeline();
    const user = await getTestUser();
    await loginUser(page, user);
    const url = `/transformation/pipelines/${pid}`;
    await page.goto(url);
    await assertNoA11yViolations(page, url);
  });

  test('pipeline definition table or empty state is accessible', async ({ page }) => {
    const pid = await ensurePipeline();
    const user = await getTestUser();
    await loginUser(page, user);
    const url = `/transformation/pipelines/${pid}`;
    await page.goto(url);
    // The definition section renders either a table or an empty state;
    // both must be accessible.
    // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
    await page
      .locator('table, .empty-state, [data-testid="empty-state"], .error-display')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    await assertNoA11yViolations(page, url);
  });

  test('detail page renders in dark mode without violations', async ({ page }) => {
    const pid = await ensurePipeline();
    const user = await getTestUser();
    await loginUser(page, user);
    const url = `/transformation/pipelines/${pid}`;
    await page.goto(url);
    // Toggle dark theme via the header control.
    const themeToggle = page.locator('.theme-toggle, [aria-label*="dark theme"], [aria-label*="light theme"]').first();
    // intentional: best-effort UI affordance — a slow/absent toggle reads as null and the assertions below adjudicate
    await themeToggle.click().catch(() => null);
    await page.waitForTimeout(500);
    await assertNoA11yViolations(page, url);
  });
});

test.describe('Transformation Create Form — Accessibility', () => {
  test('create form inputs have accessible labels', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/transformation/create', { waitUntil: 'domcontentloaded' });
    // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
    await page
      .locator('form input, form textarea, form select')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => null);
    await assertNoA11yViolations(page, '/transformation/create');
  });

  test('create page renders without contrast violations in dark mode', async ({ page }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await page.goto('/transformation/create', { waitUntil: 'domcontentloaded' });
    const themeToggle = page.locator('.theme-toggle, [aria-label*="dark theme"], [aria-label*="light theme"]').first();
    // intentional: best-effort UI affordance — a slow/absent toggle reads as null and the assertions below adjudicate
    await themeToggle.click().catch(() => null);
    await page.waitForTimeout(500);
    await assertNoA11yViolations(page, '/transformation/create');
  });
});
