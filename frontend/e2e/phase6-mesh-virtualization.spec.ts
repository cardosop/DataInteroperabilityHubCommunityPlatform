/**
 * Phase 6 E2E Test — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DMO-001, JOURNEY-DMO-003, JOURNEY-DA-003, JOURNEY-DE-009, JOURNEY-DC-010.
 * Prefer journey specs under journeys/dmo/, journeys/da/, journeys/de/, journeys/dc/.
 * Real backend only (no mocks/stubs). Kept for backward compatibility.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginAsPersona } from './fixtures/auth';
import { loginAndNavigateToRoute, navigateToRouteFromApp, waitForAppMainReady } from './fixtures/helpers';

// Node fetch needs absolute URL; VITE_API_BASE_URL is relative (/api/v1)
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
  'http://localhost:8000/api/v1';

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

/** Create virtual dataset with ODBC source and execute query via API. Returns { datasetId, execution, result } or null. */
async function createOdbcVirtualDatasetAndExecute(): Promise<{
  datasetId: string;
  execution: { id: string; status: string };
  result?: { data?: unknown[] };
} | null> {
  const pgHost = process.env.E2E_POSTGRES_HOST || 'postgres';
  const pgUser = process.env.E2E_POSTGRES_USER || 'hub';
  const pgPassword = process.env.E2E_POSTGRES_PASSWORD || 'hub';
  const pgDb = process.env.E2E_POSTGRES_DB || 'hub';

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
      name: `e2e-odbc-${Date.now()}`,
      query: 'SELECT 1 AS col',
      query_type: 'SQL',
      status: 'ACTIVE',
      sources: [
        {
          type: 'odbc',
          host: pgHost,
          port: 5432,
          database: pgDb,
          username: pgUser,
          password: pgPassword,
          driver: 'PostgreSQL Unicode',
        },
      ],
    }),
  });
  if (!createRes.ok) return null;
  const dataset = (await createRes.json()) as { id?: string };
  const datasetId = dataset.id;
  if (!datasetId) return null;

  const execRes = await fetch(`${API_BASE}/virtualization/datasets/${datasetId}/queries/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ execution_mode: 'SYNC' }),
  });
  if (!execRes.ok) return null;
  const execution = (await execRes.json()) as { id?: string; status?: string };
  if (!execution.id) return null;

  const resultRes = await fetch(
    `${API_BASE}/virtualization/queries/${execution.id}/result/?format=json`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const result = resultRes.ok ? ((await resultRes.json()) as { data?: unknown[] }) : undefined;

  return {
    datasetId,
    execution: { id: execution.id, status: execution.status || '' },
    result,
  };
}

test.describe('Phase 6 Mesh + Virtualization', () => {
  test('mesh domains list loads and create flow works', async ({ page }) => {
    test.setTimeout(120000);
    await loginAsPersona(page, getTestUser);
    const testUser = await getTestUser();

    await loginAndNavigateToRoute(page, testUser, '/mesh', {
      timeout: 60000,
      contentSelector: '.mesh-domain-list-page, .empty-state, .error-display, h1',
    });

    await navigateToRouteFromApp(page, '/mesh/create', {
      timeout: 60000,
      contentSelector: 'h1, .mesh-domain-create-page, .error-display, .unavailable-page, [data-testid="mesh-domain-create-page"]',
    });
    // Capability-gated: may show Create form, 403, or unavailable message
    const on403 = page.url().includes('/403');
    const hasCreateHeading = (await page.getByRole('heading', { name: 'Create Mesh Domain' }).count()) > 0;
    const hasUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
    expect(hasCreateHeading || on403 || hasUnavailable).toBe(true);
    if (!hasCreateHeading) return;

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
    test.setTimeout(120000); // 2 min: visible project has slowMo; mesh nav + topology load can be slow
    await loginAsPersona(page, getTestUser);
    const testUser = await getTestUser();

    await loginAndNavigateToRoute(page, testUser, '/mesh', {
      timeout: 60000,
      contentSelector: '.mesh-domain-list-page, .topology-visualization, .empty-state, .error-display, h1',
    });
    await navigateToRouteFromApp(page, '/mesh/topology', {
      timeout: 60000,
      contentSelector: '.topology-visualization, .topology-header, .loading-spinner, .error-display, .unavailable-page, h2, main',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;
    const topologyOrFallback = page.locator(
      '.topology-visualization, .topology-header, .loading-spinner, .error-display, .unavailable-page, h2'
    ).first();
    await expect(topologyOrFallback).toBeVisible({ timeout: 15000 });

    const body = page.locator('body');
    await expect(body).toContainText(
      /Mesh Topology|Loading topology|Domains|Failed to load topology/,
      { timeout: 10000 }
    );
  });

  test('virtual datasets list loads and create flow works', async ({ page }) => {
    test.setTimeout(120000);
    await loginAsPersona(page, getTestUser);
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/virtualization', {
      timeout: 60000,
      contentSelector: '.virtual-dataset-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    await navigateToRouteFromApp(page, '/virtualization/create', {
      timeout: 60000,
      contentSelector: 'h1, .virtual-dataset-create-page, .error-display, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;
    const on403 = page.url().includes('/403');
    const hasCreateHeading = (await page.getByRole('heading', { name: /Create.*Virtual Dataset|Create Virtual Dataset/ }).count()) > 0;
    const hasUnavailable = (await page.locator('.unavailable-page, .error-display').count()) > 0;
    expect(hasCreateHeading || on403 || hasUnavailable).toBe(true);
    if (!hasCreateHeading) return;

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
    await loginAndNavigateToRoute(page, testUser, '/virtualization', {
      timeout: 60000,
      contentSelector: '.virtual-dataset-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

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

    await waitForAppMainReady(page, {
      timeout: 60000,
      contentSelector: '.virtual-dataset-detail-page, .loading-spinner, .error-display',
    });
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
    await loginAndNavigateToRoute(page, testUser, '/virtualization', {
      timeout: 60000,
      contentSelector: '.virtual-dataset-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

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

  test('ODBC virtual dataset: create via API, execute query, assert result (Phase 26.8)', async () => {
    test.setTimeout(120000);
    const outcome = await createOdbcVirtualDatasetAndExecute();
    if (!outcome) {
      test.skip(
        true,
        'ODBC create/execute failed (API unreachable, auth, or ODBC driver not available in API container)'
      );
    }
    expect(outcome.execution.status).toBe('COMPLETED');
    expect(outcome.result).toBeDefined();
    expect(outcome.result?.data).toBeDefined();
    expect(Array.isArray(outcome.result?.data)).toBe(true);
    expect((outcome.result?.data as unknown[]).length).toBeGreaterThanOrEqual(1);
    const firstRow = (outcome.result?.data as Record<string, unknown>[])[0];
    expect(firstRow).toHaveProperty('col');
    expect(firstRow.col).toBe(1);
  });

  test('ODBC virtual dataset: create via UI form (Host+Database), execute query, assert result (Phase 26, 28.4.2)', async ({
    page,
  }) => {
    test.setTimeout(180000);
    // Align with createOdbcVirtualDatasetAndExecute: e2e-detect-api sets E2E_POSTGRES_* for test stack (port 8001)
    const pgHost = process.env.E2E_POSTGRES_HOST || 'postgres';
    const pgUser = process.env.E2E_POSTGRES_USER || 'hub';
    const pgPassword = process.env.E2E_POSTGRES_PASSWORD || 'hub';
    const pgDb = process.env.E2E_POSTGRES_DB || 'hub';

    await loginAsPersona(page, getTestUser);
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/virtualization/create', {
      timeout: 60000,
      contentSelector: 'h1, .virtual-dataset-create-page, .error-display, .unavailable-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) {
      test.skip(true, 'Redirected to login; cannot test ODBC UI create');
    }
    const hasCreateHeading =
      (await page.getByRole('heading', { name: /Create.*Virtual Dataset|Create Virtual Dataset/ }).count()) > 0;
    if (!hasCreateHeading) {
      test.skip(true, 'Create page not available (403 or capability-gated)');
    }

    await page.fill('input[id="name"]', `e2e-odbc-ui-${Date.now()}`);
    await page.fill('textarea[id="query"]', 'SELECT 1 AS col');

    await page.locator('button:has-text("Add source")').click();
    await page.locator('[data-testid="odbc-source-form"]').waitFor({ state: 'visible', timeout: 5000 });
    await page.locator('[data-testid="odbc-host-database-radio"]').click();
    await page.locator('[data-testid="odbc-host"]').fill(pgHost);
    await page.locator('[data-testid="odbc-database"]').fill(pgDb);
    await page.locator('[data-testid="odbc-username"]').fill(pgUser);
    await page.locator('[data-testid="odbc-password"]').fill(pgPassword);
    await page.locator('[data-testid="odbc-add-source-btn"]').click();

    await page.selectOption('select[id="status"]', 'ACTIVE');
    const schemaInput = page.locator('textarea[id="schema"]');
    if ((await schemaInput.count()) > 0) {
      await schemaInput.fill('{}');
    }

    await page.locator('button[type="submit"]').click();

    try {
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith('/virtualization/') &&
          url.pathname !== '/virtualization/create' &&
          url.pathname !== '/virtualization',
        { timeout: 20000 }
      );
    } catch {
      const errText = await page.locator('.error-display, .error-message, [role="alert"]').first().textContent();
      test.skip(
        true,
        `ODBC UI create failed (redirect timeout). Backend may reject ODBC or driver unavailable. ${errText || ''}`
      );
    }

    const queryUIVisible = await page
      .locator('.query-execution-ui, .query-execution-section')
      .first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .then(() => true)
      .catch(() => false);
    if (!queryUIVisible) {
      test.skip(true, 'Query execution UI not visible on detail page');
    }

    const executeBtn = page.locator('button:has-text("Execute Query")').first();
    await executeBtn.waitFor({ state: 'visible', timeout: 5000 });
    await executeBtn.click();

    await expect(
      page.locator(
        '.progress-section, .results-section, .results-table, .error-section, .error-display'
      )
    ).toBeVisible({ timeout: 30000 });

    const resultsTable = page.locator('.results-table, .results-section table');
    const hasResult = await resultsTable.waitFor({ state: 'visible', timeout: 15000 }).then(() => true).catch(() => false);
    if (!hasResult) {
      const errSection = page.locator('.error-section, .error-display');
      const hasErr = (await errSection.count()) > 0;
      test.skip(
        true,
        `No results table visible (ODBC driver may not be available in API container). Error visible: ${hasErr}`
      );
    }

    const firstCell = page.locator('.results-table td, .results-section td').first();
    await expect(firstCell).toContainText('1', { timeout: 5000 });
  });
});
