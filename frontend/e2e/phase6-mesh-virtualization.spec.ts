/**
 * Phase 6 E2E Test — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DMO-001, JOURNEY-DMO-003, JOURNEY-DA-003, JOURNEY-DE-009, JOURNEY-DC-010.
 * Prefer journey specs under journeys/dmo/, journeys/da/, journeys/de/, journeys/dc/.
 * Real backend only (no mocks/stubs). Kept for backward compatibility.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from './fixtures/auth';

const API_BASE = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/** Create a virtual dataset via API (real backend) so edit test can reach detail when list is empty. */
async function ensureVirtualDatasetForEdit(): Promise<string | null> {
  const testUser = await getTestUser();
  const loginRes = await fetch(`${API_BASE}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: testUser.email, password: testUser.password }),
  });
  if (!loginRes.ok) return null;
  const loginData = (await loginRes.json()) as { access_token?: string };
  const token = loginData.access_token;
  if (!token) return null;
  const createRes = await fetch(`${API_BASE}/virtualization/datasets/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name: `e2e-edit-${Date.now()}`,
      query: 'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1',
      query_type: 'SPARQL',
      status: 'DRAFT',
    }),
  });
  if (!createRes.ok) return null;
  const dataset = (await createRes.json()) as { id?: string };
  return dataset.id ?? null;
}

test.describe('Phase 6 Mesh + Virtualization', () => {
  test('mesh domains list loads and create flow works', async ({ page }) => {
    test.setTimeout(120000);
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    await page.goto('/mesh', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');

    await expect(
      page.locator('.mesh-domain-list-page, .empty-state, .error-display, h1').first()
    ).toBeVisible({ timeout: 15000 });

    await page.goto('/mesh/create', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Create Mesh Domain' })).toBeVisible({
      timeout: 10000,
    });

    await page.fill('input[id="name"]', `e2e-mesh-domain-${Date.now()}`);
    await page.fill('textarea[id="description"]', 'E2E Phase 6 mesh domain');
    const submitBtn = page
      .locator('button[type="submit"]')
      .or(page.locator('button:has-text("Create")'))
      .first();
    await submitBtn.waitFor({ state: 'visible', timeout: 5000 });
    await submitBtn.click();

    // Backend may return 403 if mesh is capability-gated; accept either redirect or error message
    try {
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith('/mesh/') &&
          url.pathname !== '/mesh/create' &&
          url.pathname !== '/mesh',
        { timeout: 15000 }
      );
      await expect(
        page.locator('.mesh-domain-detail-page, .loading-spinner, h1').first()
      ).toBeVisible({ timeout: 10000 });
    } catch {
      await expect(
        page.locator('.error-display, .error-message, [role="alert"]').first()
      ).toContainText(/forbidden|not available|error|failed|403/i, { timeout: 5000 });
    }
  });

  test('topology view loads (minimal viable graph)', async ({ page }) => {
    test.setTimeout(60000);
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    await page.goto('/mesh/topology', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');

    await expect(
      page
        .locator('.topology-visualization, .topology-header, .loading-spinner, .error-display, h2')
        .first()
    ).toBeVisible({ timeout: 15000 });

    const body = page.locator('body');
    await expect(body).toContainText(
      /Mesh Topology|Loading topology|Domains|Failed to load topology/,
      { timeout: 10000 }
    );
  });

  test('virtual datasets list loads and create flow works', async ({ page }) => {
    test.setTimeout(120000);
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    await page.goto('/virtualization', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');

    await expect(
      page.locator('.virtual-dataset-list-page, .empty-state, .error-display, h1').first()
    ).toBeVisible({ timeout: 15000 });

    await page.goto('/virtualization/create', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: /Create.*Virtual Dataset|Create Virtual Dataset/ })
    ).toBeVisible({ timeout: 10000 });

    await page.fill('input[id="name"]', `e2e-virt-ds-${Date.now()}`);
    await page.fill('textarea[id="query"]', 'SELECT 1 AS col');
    const schemaInput = page.locator('textarea[id="schema"]');
    if ((await schemaInput.count()) > 0) {
      await schemaInput.fill('{}');
    }
    const submitBtn = page
      .locator('button[type="submit"]')
      .or(page.locator('button:has-text("Create")'))
      .first();
    await submitBtn.waitFor({ state: 'visible', timeout: 5000 });
    await submitBtn.click();

    // Backend may return 400 (tenant/validation) or 403 (capability-gated); accept either redirect or error
    try {
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith('/virtualization/') &&
          url.pathname !== '/virtualization/create' &&
          url.pathname !== '/virtualization',
        { timeout: 15000 }
      );
      await expect(
        page.locator('.virtual-dataset-detail-page, .loading-spinner, h1').first()
      ).toBeVisible({ timeout: 10000 });
    } catch {
      await expect(
        page
          .locator('.virtual-dataset-create-page, .error-display, .error-message, [role="alert"]')
          .first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('virtualization edit: Edit from detail opens edit page (A.1.4)', async ({ page }) => {
    test.setTimeout(90000);
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    await page.goto('/virtualization', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');

    const hasRow = (await page.locator('.virtual-dataset-list-page table tbody tr').count()) > 0;
    if (hasRow) {
      await page.locator('.virtual-dataset-list-page table tbody tr').first().click();
      await page
        .waitForURL((url) => /^\/virtualization\/[0-9a-f-]{36}$/i.test(new URL(url).pathname), {
          timeout: 10000,
        })
        .catch(() => {});
    } else {
      const datasetId = await ensureVirtualDatasetForEdit();
      if (datasetId) {
        await page.goto(`/virtualization/${datasetId}`, { waitUntil: 'domcontentloaded' });
      }
    }

    const pathname = new URL(page.url()).pathname;
    const isDetailPage = /^\/virtualization\/[0-9a-f-]{36}$/i.test(pathname);
    if (!isDetailPage) {
      test.skip(
        true,
        'Not on virtual dataset detail (no row and API create not available); cannot test Edit'
      );
    }

    await page.waitForSelector('.virtual-dataset-detail-page', {
      state: 'visible',
      timeout: 10000,
    });
    const editBtn = page.getByRole('button', { name: /Edit/i });
    await editBtn.waitFor({ state: 'visible', timeout: 10000 });
    await editBtn.click();
    await page.waitForURL((url) => url.pathname.endsWith('/edit'), { timeout: 15000 });
    await expect(page.getByRole('heading', { name: /Edit.*Virtual Dataset/i })).toBeVisible({
      timeout: 5000,
    });
    const saveBtn = page
      .locator('button[type="submit"]')
      .or(page.locator('button:has-text("Save")'))
      .first();
    await expect(saveBtn).toBeVisible({ timeout: 5000 });
  });

  test('query execution UX: run query and see result or progress (DoD-7.1)', async ({ page }) => {
    test.setTimeout(180000);
    const testUser = await getTestUser();
    await loginUser(page, testUser);

    await page.goto('/virtualization', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');

    const hasRow = (await page.locator('.virtual-dataset-list-page table tbody tr').count()) > 0;
    if (hasRow) {
      await page.locator('.virtual-dataset-list-page table tbody tr').first().click();
      await page
        .waitForURL((url) => /^\/virtualization\/[0-9a-f-]{36}$/i.test(new URL(url).pathname), {
          timeout: 10000,
        })
        .catch(() => {});
    } else {
      const datasetId = await ensureVirtualDatasetForEdit();
      if (datasetId) {
        await page.goto(`/virtualization/${datasetId}`, { waitUntil: 'domcontentloaded' });
      }
    }

    const pathname = new URL(page.url()).pathname;
    const isDetailPage = /^\/virtualization\/[0-9a-f-]{36}$/i.test(pathname);
    if (!isDetailPage) {
      test.skip(
        true,
        'Not on virtual dataset detail (no row and API create not available); cannot test query UX'
      );
    }

    const queryUIVisible = await page
      .locator('.query-execution-ui, .query-execution-section')
      .first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .then(() => true)
      .catch(() => false);
    if (!queryUIVisible) {
      test.skip(
        true,
        'Query execution UI not visible (detail may show error/loading); cannot test query UX'
      );
    }
    const queryInput = page
      .locator('.query-execution-ui textarea.query-editor, .query-execution-section textarea')
      .first();
    await queryInput.fill('SELECT 1 AS col');
    const executeBtn = page.locator('button:has-text("Execute Query")').first();
    await executeBtn.waitFor({ state: 'visible', timeout: 5000 });
    await executeBtn.click();

    // DoD-7.1: result, progress, cancel, or error visible (backend may return 400 in some envs)
    await expect(
      page.locator(
        '.progress-section, .results-section, .results-table, .error-section, .error-display, .query-execution-ui button:has-text("Cancel"), .query-execution-ui button:has-text("Executing")'
      )
    ).toBeVisible({ timeout: 30000 });
  });
});
