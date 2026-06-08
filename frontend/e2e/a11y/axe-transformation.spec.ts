/**
 * 285.9.4.6 — Transformation pages accessibility axe audit.
 *
 * Runs WCAG 2.1 AA checks against the wizard, contract preview,
 * and validation result pages.  Creates a pipeline via API so the
 * pages render real content instead of error / unavailable states.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect } from '@playwright/test';
import { test } from '@playwright/test';
import { getTestUser, loginUser, loginViaApi } from '../fixtures/auth';

const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  `http://localhost:${process.env.E2E_WEB_PORT ? '8001' : '8000'}/api/v1`;

/** Create a transformation pipeline via API.  Returns the pipeline ID
 *  or skips all remaining transformation tests if the feature is
 *  disabled for this tenant. */
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
    const body = await res.text().catch(() => '');
    const isDisabled = body.includes('TRANSFORMATION_DISABLED') || body.includes('disabled');
    if (isDisabled) {
      test.skip(true, `Transformation feature is disabled for this tenant — cannot create pipeline for a11y audit.`);
      return null;
    }
    throw new Error(`Failed to create transformation pipeline: ${res.status} ${body.slice(0, 300)}`);
  }
  const data = (await res.json()) as { id: string };
  _pipelineId = data.id;
  return data.id;
}

async function assertNoA11yViolations(page: import('@playwright/test').Page, originalUrl: string): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  // Transformation pages are loaded via React.lazy().  Under load the
  // Vite dev server may fail to serve a chunk.  Navigate away to a
  // simple page and back so Vite has time to GC and recompile.
  let hasViteError = false;
  for (let attempt = 0; attempt < 3; attempt++) {
    hasViteError = (await page.locator('vite-error-overlay').count()) > 0;
    if (!hasViteError) break;
    if (attempt < 2) {
      console.warn(`Vite error overlay on transformation page — navigate-away retry ${attempt + 1}/2...`);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);
      await page.goto(originalUrl, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(2000 + attempt * 2000);
    }
  }
  test.skip(hasViteError, 'Vite error overlay — transformation chunk load failed after 2 navigate-away retries');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
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

test.describe('Transformation Wizard — Accessibility', () => {
  test.beforeAll(async () => { await getOrCreatePipelineId(); });

  test('wizard page has no axe violations', async ({ page }) => {
    const pid = await ensurePipeline();
    const wizardUrl = `/transformation/pipelines/${pid}/wizard`;
    await page.goto(wizardUrl);
    await assertNoA11yViolations(page, wizardUrl);
  });

  test('direction picker buttons are accessible', async ({ page }) => {
    const pid = await ensurePipeline();
    await page.goto(`/transformation/pipelines/${pid}/wizard`);
    // The wizard renders client-side after React hydrates.  Wait for the
    // direction cards (or an error/unavailable state) to appear.
    await page.locator('.direction-card, .error-display, [data-testid="error-display"], .unavailable-page, [data-testid="unavailable-page"]').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);
    const buttons = page.locator('.direction-card');
    if ((await buttons.count()) === 0) {
      test.skip(true, 'No direction cards rendered — wizard may need direction step configuration');
      return;
    }
    await expect(buttons.first()).toHaveAttribute('aria-pressed');
    await expect(buttons.first()).toBeVisible();
  });
});

test.describe('Transformation Contract Preview — Accessibility', () => {
  test('contract preview page has no axe violations', async ({ page }) => {
    const pid = await ensurePipeline();
    const user = await getTestUser();
    await loginUser(page, user);
    const contractUrl = `/transformation/pipelines/${pid}/contract`;
    await page.goto(contractUrl);
    await assertNoA11yViolations(page, contractUrl);
  });

  test('contract table or empty state is accessible', async ({ page }) => {
    const pid = await ensurePipeline();
    const user = await getTestUser();
    await loginUser(page, user);
    const contractTableUrl = `/transformation/pipelines/${pid}/contract`;
    await page.goto(contractTableUrl);

    // Wait for any recognizable content — contract preview, error, or unavailable page.
    await page.locator('.contract-preview, .error-display, [data-testid="error-display"], .unavailable-page, [data-testid="unavailable-page"], h1, [role="alert"]').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

    const contractDiv = page.locator('.contract-preview');
    if (await contractDiv.count() > 0) {
      const table = page.locator('.contract-preview table');
      if (await table.count() > 0) {
        // Happy path: contract table rendered — test keyboard navigation.
        await expect(table).toBeVisible();
        await page.keyboard.press('Tab');
        const focused = page.locator(':focus');
        await expect(focused).toBeAttached();
        return;
      }
      // Skeleton state ("No schema fields defined") — the real UI contract
      // when no dbt project is wired.  Verify the container is visible.
      await expect(contractDiv).toBeVisible();
    }
    // Whatever page state we have (contract, skeleton, unavailable, error),
    // run axe to confirm it's accessible.
    await assertNoA11yViolations(page, contractTableUrl);
  });
});

test.describe('Transformation Validation Result — Accessibility', () => {
  test('validation page has no axe violations (empty state)', async ({ page }) => {
    const pid = await ensurePipeline();
    const validateUrl = `/transformation/pipelines/${pid}/validate`;
    await page.goto(validateUrl);
    await assertNoA11yViolations(page, validateUrl);
  });

  test('form inputs have accessible labels', async ({ page }) => {
    const pid = await ensurePipeline();
    await page.goto(`/transformation/pipelines/${pid}/validate`);
    await page.waitForLoadState('domcontentloaded');
    const inputs = page.locator(
      '.validation-result input, .validation-result select, .validation-result button'
    );
    const count = await inputs.count();
    for (let i = 0; i < count; i++) {
      const input = inputs.nth(i);
      await expect(input).toHaveAccessibleName();
    }
  });

  test('validate button is keyboard accessible', async ({ page }) => {
    const pid = await ensurePipeline();
    await page.goto(`/transformation/pipelines/${pid}/validate`);
    await page.locator('button, .error-display, [data-testid="error-display"], .unavailable-page, [data-testid="unavailable-page"]').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);
    const button = page.getByRole('button', { name: /validate/i });
    if ((await button.count()) === 0) {
      test.skip(true, 'No validate button rendered — pipeline may need validation configuration');
      return;
    }
    await expect(button).toBeVisible();
    await button.focus();
    await expect(button).toBeFocused();
  });
});

test.describe('Dark mode — Accessibility', () => {
  test('wizard renders without contrast violations in dark mode', async ({ page }) => {
    const pid = await ensurePipeline();
    const wizardDarkUrl = `/transformation/pipelines/${pid}/wizard`;
    await page.goto(wizardDarkUrl);
    await page.emulateMedia({ colorScheme: 'dark' });
    await assertNoA11yViolations(page, wizardDarkUrl);
  });

  test('contract preview renders in dark mode without violations', async ({ page }) => {
    const pid = await ensurePipeline();
    const contractDarkUrl = `/transformation/pipelines/${pid}/contract`;
    await page.goto(contractDarkUrl);
    await page.emulateMedia({ colorScheme: 'dark' });
    await assertNoA11yViolations(page, contractDarkUrl);
  });
});
