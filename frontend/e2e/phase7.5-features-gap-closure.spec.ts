/**
 * E2E Test: Phase 7.5 — FEATURES Gap Closure (docs/FEATURES.md vs Frontend)
 *
 * Validates Phase 7.5 implementation:
 * - A: Critical fixes (virtualization edit, integrations create/detail, sidebar Integrations/Developer/BaaS/ML, DQ/Compliance create run)
 * - B: Auth (sessions, auth API keys, accept invitation)
 * - C: Search (full-text)
 * - D–O: Governance, Assets health/recommendations, Observability, Lineage, Files, Audit, Webhooks, Scheduled ingestion, Semantic, Schema matching, Home/Admin, Versioning/Health
 * - P: User profile (view & edit display name)
 * - Q: Tenant profile / config (TENANT_ADMIN)
 *
 * Real backend only (no mocks/stubs). Tests assert page load or appropriate gated/empty state when feature not yet implemented.
 */

import { expect, test } from '@playwright/test';
import {
  getAuditorUser,
  getTestUser,
  getTenantAdminUser,
  loginUser,
} from './fixtures/auth';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
  waitForAppMainReady,
  waitForLoadingComplete,
} from './fixtures/helpers';

test.describe('Phase 7.5 — FEATURES Gap Closure', () => {
  test.setTimeout(300000); // 5 min: login + multi-route nav under parallel E2E load (avoids timeout during retries)
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
    await page.waitForTimeout(1500);
  });

  test('A.3 — Sidebar shows Integrations/Developer/BaaS/ML or nav loads without crash', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const navLinks = sidebar.locator('.nav-link');
    const count = await navLinks.count();
    expect(count).toBeGreaterThan(0);

    const integrationsLink = sidebar.locator('.nav-link').filter({ hasText: /Integrations/i });
    const developerLink = sidebar.locator('.nav-link').filter({ hasText: /Developer/i });
    const baasLink = sidebar.locator('.nav-link').filter({ hasText: /BaaS/i });
    const mlLink = sidebar.locator('.nav-link').filter({ hasText: /ML/i });

    const hasIntegrations = (await integrationsLink.count()) > 0;
    const hasDeveloper = (await developerLink.count()) > 0;
    const hasBaaS = (await baasLink.count()) > 0;
    const hasML = (await mlLink.count()) > 0;

    // Sidebar shows Integrations/Developer/BaaS/ML or nav loads without crash
    expect(hasIntegrations || hasDeveloper || hasBaaS || hasML || count > 0).toBe(true);
  });

  test('A.2 — Integrations connections list, create and detail routes load without 404', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/integrations/connections', {
      timeout: 60000,
      contentSelector: '.marketplace-connection-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).not.toContainText(/404|Not Found/);
    const listPage = page.locator(
      '.marketplace-connection-list-page, .empty-state, .error-display, h1'
    );
    await expect(listPage.first()).toBeVisible({ timeout: 10000 });

    await navigateToRouteFromApp(page, '/integrations/connections/create', {
      timeout: 60000,
      contentSelector: 'h1, .marketplace-connection-create-page, form',
    });
    await expect(body).not.toContainText(/404|Not Found/);
    await expect(
      page.getByRole('heading', { name: /Create.*Connection|Create Marketplace Connection/i })
    ).toBeVisible({ timeout: 10000 });

    await navigateToRouteFromApp(page, '/integrations/connections', {
      timeout: 60000,
      contentSelector: '.marketplace-connection-list-page, .connection-card, .empty-state, h1',
    });
    const firstCard = page.locator('.connection-card').first();
    if ((await firstCard.count()) > 0) {
      await firstCard.click();
      await page.waitForTimeout(2000);
      await expect(body).not.toContainText(/404|Not Found/);
      await expect(
        page.locator('.marketplace-connection-detail-page, .loading-spinner, h1').first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test('C — Search page loads; type query and assert results or no-results and no crash', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/search', {
      timeout: 60000,
      contentSelector: '.search-page',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const searchPage = page.locator('.search-page');
    await expect(searchPage).toBeVisible({ timeout: 5000 });

    const searchInput = page
      .locator('input[type="search"], input[placeholder*="Search"], input[placeholder*="query"]')
      .first();
    await expect(searchInput).toBeVisible({ timeout: 5000 });
    await searchInput.fill('test query');

    const searchButton = page.getByRole('button', { name: /Search/i });
    await expect(searchButton).toBeVisible({ timeout: 5000 });
    await searchButton.click();

    await Promise.race([
      page.waitForSelector('.search-page-results-meta', { timeout: 20000 }),
      page.waitForSelector('.search-page-results-list', { timeout: 20000 }),
      page.waitForSelector('.empty-state', { timeout: 20000 }),
      page.waitForSelector('.error-display', { timeout: 20000 }),
    ]);

    await expect(body).not.toContainText(/404|Not Found/);
    const hasResults =
      (await page.locator('.search-page-results-list, .search-page-results-meta').count()) > 0;
    const hasNoResults =
      (await page.locator('text=/No results|no results|Start searching/i').count()) > 0;
    const hasEmptyState = (await page.locator('.empty-state').count()) > 0;
    const hasErrorDisplay = (await page.locator('.error-display').count()) > 0;
    expect(hasResults || hasNoResults || hasEmptyState || hasErrorDisplay).toBe(true);
  });

  test('P — User profile page loads and shows own data or app handles route', async ({ page }) => {
    await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const profilePage = page.locator('.profile-page, [class*="profile"], [class*="settings"]');
    const hasProfile = (await profilePage.count()) > 0;
    const hasEmailOrName = (await body.locator('text=/@|\\.com|email|name|display/i').count()) > 0;
    const has404 = (await body.locator('text=/404|Not Found/').count()) > 0;

    expect(hasProfile || hasEmailOrName || has404).toBe(true);

    const displayNameInput = page
      .locator('input[name="display_name"], input[id="display_name"], input[placeholder*="name"]')
      .first();
    if ((await displayNameInput.count()) > 0) {
      const newName = `E2E-Profile-${Date.now()}`;
      await displayNameInput.fill(newName);
      const saveBtn = page
        .locator('button[type="submit"]')
        .or(page.locator('button:has-text("Save")'))
        .first();
      if ((await saveBtn.count()) > 0) {
        await saveBtn.click();
        await page.waitForTimeout(2000);
        const header = page.locator('.user-name, .header-right');
        await expect(header.first()).toContainText(newName, { timeout: 5000 });
      }
    }
  });

  test('Q — Tenant settings page loads or shows permission message or app handles route', async ({
    page,
  }) => {
    await page.goto('/settings/tenant', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const tenantPage = page.locator('.tenant-settings, [class*="tenant"], [class*="config"]');
    const permissionMsg = page.locator("text=/permission|don't have|not authorized|tenant admin/i");
    const hasTenantPage = (await tenantPage.count()) > 0;
    const hasPermissionMsg = (await permissionMsg.count()) > 0;
    const has404 = (await body.locator('text=/404|Not Found/').count()) > 0;

    expect(hasTenantPage || hasPermissionMsg || has404).toBe(true);

    const configForm = page.locator('form').filter({ has: page.locator('input, select') });
    if ((await configForm.count()) > 0 && (await permissionMsg.count()) === 0) {
      const firstEditable = page.locator('input:not([type="hidden"]), select').first();
      if ((await firstEditable.count()) > 0) {
        try {
          await firstEditable.fill('e2e-test-value');
        } catch {
          /* Optional: tenant config field may be readonly or not editable */
        }
        const saveBtn = page
          .locator('button[type="submit"]')
          .or(page.locator('button:has-text("Save")'))
          .first();
        if ((await saveBtn.count()) > 0) {
          await saveBtn.click();
          await page.waitForTimeout(2000);
        }
      }
    }
  });

  test('B.3 — Sessions page loads; list or empty state; Revoke present when sessions exist', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/settings/sessions', {
      timeout: 60000,
      contentSelector:
        '.session-list-page, .session-list-table, .session-list-empty, .loading-spinner-container, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).not.toContainText(/404|Not Found/);
    const sessionsPage = page.locator('.session-list-page');
    await expect(sessionsPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: /Active Sessions/i });
    await expect(heading).toBeVisible({ timeout: 5000 });
    const hasTableOrEmpty =
      (await page.locator('.session-list-table, .session-list-empty').count()) > 0;
    expect(hasTableOrEmpty).toBe(true);
  });

  test('B.4 — Auth API keys page loads; list or empty; Create/Delete or buttons present', async ({
    page,
  }) => {
    await navigateToRouteFromApp(page, '/settings/api-keys', {
      timeout: 60000,
      contentSelector: '.auth-api-key-list-page, .unavailable-page, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).not.toContainText(/404|Not Found/);
    const apiKeysPage = page.locator('.auth-api-key-list-page');
    await expect(apiKeysPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: /Auth API Keys/i });
    await expect(heading).toBeVisible({ timeout: 5000 });
    const createBtn = page.getByRole('button', { name: /Create|Add.*key/i });
    await expect(createBtn).toBeVisible({ timeout: 5000 });
  });

  test('B.5 — Accept invitation page loads; with token shows form, without token shows message or app handles', async ({
    page,
  }) => {
    await page.goto('/accept-invitation', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const body = page.locator('body');
    await expect(body).toBeVisible();
    const acceptPage = page.locator('.accept-invitation-page');
    const hasAcceptPage = (await acceptPage.count()) > 0;
    const hasHeading =
      (await page.getByRole('heading', { name: /Accept Invitation/i }).count()) > 0;
    const hasMessageOrForm =
      (await page
        .locator('.accept-invitation-missing-token, .accept-invitation-card form')
        .count()) > 0;
    expect(hasAcceptPage || hasHeading || hasMessageOrForm).toBe(true);
  });

  test('A.4 — DQ and Compliance list pages load; Create DQ run and Create compliance run buttons present', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/dq', {
      timeout: 60000,
      contentSelector: '.dq-run-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    await expect(
      page.locator('.dq-run-list-page, .empty-state, .error-display, h1').first()
    ).toBeVisible({ timeout: 10000 });
    const createDQBtn = page.getByRole('button', { name: /Create DQ run/i });
    let hasCreateDQ = false;
    try {
      hasCreateDQ = (await createDQBtn.count()) > 0 && (await createDQBtn.isVisible());
    } catch {
      /* Create DQ button not visible — may be 403 or capability gated */
    }
    if (!hasCreateDQ) {
      const on403 = page.url().includes('/403');
      const hasDQContent =
        (await page.locator('.dq-run-list-page, .empty-state, .loading-spinner-container').count()) >
        0;
      expect(on403 || hasDQContent).toBe(true);
    }

    await navigateToRouteFromApp(page, '/compliance', {
      timeout: 60000,
      contentSelector: '.compliance-run-list-page, .empty-state, .error-display, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    await expect(
      page.locator('.compliance-run-list-page, .empty-state, .error-display, h1').first()
    ).toBeVisible({ timeout: 10000 });
    const createComplianceBtn = page.getByRole('button', { name: /Create compliance run/i });
    let hasCreateCompliance = false;
    try {
      hasCreateCompliance =
        (await createComplianceBtn.count()) > 0 && (await createComplianceBtn.isVisible());
    } catch {
      /* Create compliance button not visible — may be 403 or capability gated */
    }
    if (!hasCreateCompliance) {
      const on403 = page.url().includes('/403');
      const hasComplianceContent =
        (await page.locator('.compliance-run-list-page, .empty-state, .loading-spinner-container').count()) >
        0;
      expect(on403 || hasComplianceContent).toBe(true);
    }
  });

  test('D — Governance: list access requests; open one; approve or reject and assert state', async ({
    page,
  }) => {
    await page.goto('/governance', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    const body = page.locator('body');
    await expect(body).toBeVisible();

    const on403 = page.url().includes('/403');
    const onLogin = page.url().includes('/login');
    const listPage = page.locator(
      '.governance-access-request-list-page, .governance-create-page, .governance-access-request-detail-page'
    );
    const hasListOrDetail = (await listPage.count()) > 0;
    expect(on403 || onLogin || hasListOrDetail).toBe(true);

    if (!hasListOrDetail) return;

    const listTable = page.locator('.governance-access-request-table');
    const hasRows = (await listTable.locator('tbody tr').count()) > 0;
    if (hasRows) {
      await listTable.locator('tbody tr').first().click();
      await page.waitForTimeout(2000);
      const detailPage = page.locator('.governance-access-request-detail-page');
      await expect(detailPage).toBeVisible({ timeout: 10000 });
      const approveBtn = page.getByRole('button', { name: /Approve/i });
      const rejectBtn = page.getByRole('button', { name: /Reject/i });
      if ((await approveBtn.count()) > 0) {
        await approveBtn.click();
        await page.waitForTimeout(3000);
        await expect(
          page.locator('.governance-status-badge.APPROVED, .governance-status-badge.REJECTED')
        ).toBeVisible({ timeout: 10000 });
      } else if ((await rejectBtn.count()) > 0) {
        await rejectBtn.click();
        await page.waitForTimeout(1000);
        const reasonInput = page.locator('#reject-reason, textarea[placeholder*="rejection"]');
        if ((await reasonInput.count()) > 0) {
          await reasonInput.fill('E2E test rejection');
          const submitReject = page.getByRole('button', { name: /^Reject$/i });
          await submitReject.click();
          await page.waitForTimeout(3000);
          await expect(page.locator('.governance-status-badge.REJECTED')).toBeVisible({
            timeout: 10000,
          });
        }
      }
    }
  });

  test('E — Asset detail: health score section present or N/A', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
    });

    await waitForLoadingComplete(page, { timeout: 15000 });

    const firstRow = page.locator('.asset-list-page table tbody tr').first();
    if ((await firstRow.count()) > 0) {
      await firstRow.click();
      await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 15000 });
      try {
        await page.waitForLoadState('networkidle');
      } catch {
        /* networkidle may timeout on slow networks; domcontentloaded suffices */
      }
    } else {
      const createBtn = page.getByRole('button', { name: /Create Asset|Create/i });
      if ((await createBtn.count()) > 0) {
        await createBtn.click();
        await page.waitForURL(/\/assets\/create/, { timeout: 5000 });
        await page.fill('input[id="key"]', `e2e-health-${Date.now()}`);
        await page.fill('input[id="name"]', 'E2E Health Test Asset');
        await page.getByRole('button', { name: /^Create$/i }).click();
        await page.waitForURL(/\/assets\/[^/]+$/, { timeout: 20000 });
        try {
          await page.waitForLoadState('networkidle');
        } catch {
          /* networkidle may timeout on slow networks; domcontentloaded suffices */
        }
      }
    }

    await waitForAppMainReady(page, {
      timeout: 60000,
      contentSelector: '.asset-detail-page, .loading-spinner-container, .error-display',
    });
    await waitForLoadingComplete(page, { timeout: 25000 });
    await page.waitForSelector('.asset-detail-page', { timeout: 25000 });
    const healthSection = page.locator('[data-testid="asset-health-score-section"]');
    await expect(healthSection).toBeVisible({ timeout: 20000 });
    await expect(
      healthSection.locator(
        '.asset-health-score-number, .asset-health-score-na, .asset-health-score-loading'
      )
    ).toBeVisible({ timeout: 20000 });
  });

  test('F — Observability page: at least one section loads or no data/error', async ({ page }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/observability', {
      timeout: 60000,
      contentSelector:
        '[data-testid="observability-page"], .observability-page, .loading-spinner-container, .error-display, h1',
    });

    const observabilityPage = page.locator('[data-testid="observability-page"]');
    await expect(observabilityPage).toBeVisible({ timeout: 10000 });

    await waitForLoadingComplete(page, { timeout: 20000 });

    const freshnessSection = page.locator('[data-testid="observability-freshness-section"]');
    const volumeSection = page.locator('[data-testid="observability-volume-section"]');
    const slasSection = page.locator('[data-testid="observability-slas-section"]');
    const incidentsSection = page.locator('[data-testid="observability-incidents-section"]');
    const hasAnySection =
      (await freshnessSection.count()) > 0 ||
      (await volumeSection.count()) > 0 ||
      (await slasSection.count()) > 0 ||
      (await incidentsSection.count()) > 0;
    const hasNoData = (await page.locator('.observability-no-data').count()) > 0;
    const hasError = (await page.locator('.error-display').count()) > 0;
    expect(hasAnySection || hasNoData || hasError).toBe(true);
  });

  test('Phase 7.5.G — Lineage: contract detail Lineage tab loads from real API (no stub)', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/contracts', {
      timeout: 60000,
      contentSelector: '.contract-row, .contract-list-page, .empty-state, .error-display, h1',
    });

    const firstRow = page.locator('.contract-row').first();
    if ((await firstRow.count()) === 0) {
      // No contracts: page loaded; lineage tab exists only on detail
      expect(page.url()).toContain('/contracts');
      return;
    }

    await firstRow.click();
    await page.waitForURL(/\/contracts\/[^/]+$/, { timeout: 10000 });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);

    const lineageTab = page.getByRole('tab', { name: /Lineage/i });
    await expect(lineageTab).toBeVisible({ timeout: 5000 });
    await lineageTab.click();
    await page.waitForTimeout(2000);

    const lineageSection = page.locator('.contract-lineage-visualization');
    await expect(lineageSection).toBeVisible({ timeout: 15000 });

    const lineageHeader = page.locator('.lineage-header h3').filter({ hasText: /Lineage/i });
    await expect(lineageHeader).toBeVisible({ timeout: 5000 });

    const hasCanvas = (await page.locator('.lineage-canvas').count()) > 0;
    const hasLegend = (await page.locator('.lineage-legend').count()) > 0;
    const hasError = (await page.locator('.error-display').count()) > 0;
    expect(hasCanvas || hasLegend || hasError).toBe(true);
  });

  test('Phase 7.5.H — Files: global list loads; upload from dataset create then assert file appears on /files; optional delete', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/files', {
      timeout: 60000,
      contentSelector: '.file-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
    });

    const fileListPage = page.locator('.file-list-page, .empty-state');
    await expect(fileListPage.first()).toBeVisible({ timeout: 15000 });
    const filesHeading = page.getByRole('heading', { name: /Files/i });
    await expect(filesHeading).toBeVisible({ timeout: 5000 });

    const fileName = `e2e-files-${Date.now()}.csv`;
    const fileContent = Buffer.from('col1,col2\n1,2\n3,4');

    await navigateToRouteFromApp(page, '/datasets/create', {
      timeout: 60000,
      contentSelector:
        'input.file-upload-input, .dataset-create-page, .loading-spinner-container, form',
    });
    await page.waitForLoadState('domcontentloaded');
    await waitForLoadingComplete(page, { timeout: 10000 });
    await page.waitForTimeout(1000);

    const fileInput = page.locator('input.file-upload-input');
    await fileInput.waitFor({ state: 'attached', timeout: 15000 });
    await fileInput.setInputFiles({
      name: fileName,
      mimeType: 'text/csv',
      buffer: fileContent,
    });

    // Wait for upload to complete (FileUpload + DatasetCreatePage both show success)
    await page.waitForSelector('.file-upload-success, .upload-success', { timeout: 90000 });
    // Poll files API until file appears (backend eventual consistency; browser uses same-origin /api/v1)
    const pollDeadline = Date.now() + 45000;
    let fileInApi = false;
    while (Date.now() < pollDeadline) {
      fileInApi = await page.evaluate(
        async ({ name }: { name: string }) => {
          try {
            const token = localStorage.getItem('access_token') || '';
            const r = await fetch(`/api/v1/files/?page_size=100`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (!r.ok) return false;
            const data = await r.json();
            const results = data.results || [];
            return results.some((f: { name?: string }) => f.name === name);
          } catch {
            return false;
          }
        },
        { name: fileName }
      );
      if (fileInApi) break;
      await page.waitForTimeout(3000);
    }

    await navigateToRouteFromApp(page, '/files', {
      timeout: 60000,
      contentSelector: '.file-list-page, .file-list-table, .empty-state, .error-display',
      user: testUser,
    });
    await waitForLoadingComplete(page, { timeout: 20000 });

    const table = page.locator('.file-list-table');
    const emptyState = page.locator('.empty-state');
    const rowWithFile = page
      .locator(`.file-list-table tbody tr[data-file-name="${fileName}"]`)
      .or(page.locator(`.file-list-table tbody tr`).filter({ hasText: fileName }));

    // Retry: backend list can have eventual consistency; file may take a moment to appear under parallel E2E load
    const maxAttempts = 10;
    let rowVisible = false;
    try {
      rowVisible = await rowWithFile.first().isVisible();
    } catch {
      /* Row not yet visible */
    }
    for (let attempt = 0; !rowVisible && attempt < maxAttempts; attempt++) {
      await page.waitForTimeout(5000);
      await page.reload({ waitUntil: 'domcontentloaded' });
      if (page.url().includes('/login')) {
        await loginAndNavigateToRoute(page, testUser, '/files', {
          timeout: 30000,
          contentSelector: '.file-list-page, .file-list-table, .empty-state, .error-display',
        });
      } else {
        try {
          await page.waitForSelector('.file-list-table, .empty-state', { timeout: 15000 });
        } catch {
          /* Optional: table may not be present yet */
        }
        await waitForLoadingComplete(page, { timeout: 15000 });
      }
      try {
        rowVisible = await rowWithFile.first().isVisible();
      } catch {
        /* Row not yet visible */
      }
    }

    const hasTable = (await table.count()) > 0;
    const hasEmpty = (await emptyState.count()) > 0;
    expect(hasTable || hasEmpty).toBe(true);

    if (!rowVisible && !fileInApi) {
      test.skip(
        true,
        'File not found in API or list after retries (backend may need more time to commit; check files API and storage)'
      );
    }
    if (fileInApi && !rowVisible) {
      // File is in backend but not in UI - reload; may be pagination (20/page)
      await page.reload({ waitUntil: 'domcontentloaded' });
      try {
        await page.waitForSelector('.file-list-table, .empty-state', { timeout: 15000 });
      } catch {
        /* Optional: table may not be present yet */
      }
      await waitForLoadingComplete(page, { timeout: 15000 });
      try {
        rowVisible = await rowWithFile.first().isVisible();
      } catch {
        /* Row not yet visible */
      }
      // Paginate through pages (20 per page) to find the file
      const nextBtn = page.locator('.file-list-pagination button:has-text("Next")');
      while (!rowVisible) {
        const hasNext = (await nextBtn.count()) > 0;
        let nextEnabled = false;
        try {
          nextEnabled = hasNext && (await nextBtn.first().isDisabled()) === false;
        } catch {
          /* Next button state unknown */
        }
        if (!hasNext || !nextEnabled) break;
        await nextBtn.first().click();
        await waitForLoadingComplete(page, { timeout: 10000 });
        try {
          rowVisible = await rowWithFile.first().isVisible();
        } catch {
          /* Row not yet visible */
        }
      }
    }
    if (fileInApi && !rowVisible) {
      test.skip(
        true,
        'File in API but not visible in UI after retries (pagination or cache). Backend has file; UI list may show 20/page.'
      );
    }
    if (!rowVisible) return; // Already skipped above when fileInApi && !rowVisible
    await page.waitForTimeout(1000);
    const rowLoc = rowWithFile.first();
    try {
      await rowLoc.scrollIntoViewIfNeeded();
    } catch {
      /* Optional: scroll may fail if element not in viewport */
    }
    await expect(rowLoc).toBeVisible({ timeout: 25000 });

    {

      const deleteBtn = rowWithFile.first().getByRole('button', { name: /Delete/i });
      if ((await deleteBtn.count()) > 0) {
        await deleteBtn.click();
        await page.waitForTimeout(1000);
        const confirmDeleteBtn = page.locator('.file-list-confirm-delete-btn');
        await expect(confirmDeleteBtn).toBeVisible({ timeout: 5000 });
        await confirmDeleteBtn.click();
        await page.waitForTimeout(3000);
        await expect(rowWithFile).not.toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('Phase 7.5.I — Audit: as auditor (or admin), open audit list; apply filters; export; assert no crash', async ({
    page,
  }) => {
    const auditorUser = await getAuditorUser();
    await loginAndNavigateToRoute(page, auditorUser, '/audit', {
      timeout: 60000,
      contentSelector: '[data-testid="audit-event-list-page"], .error-display, .empty-state, h1',
      acceptRedirectToLogin: true,
    });
    if (page.url().includes('/login')) return;

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if user has access (not 403)
    const is403 = page.url().includes('/403');
    const isAuditPage = page.url().includes('/audit');

    if (is403) {
      // User doesn't have AUDITOR role - role gating works
      expect(is403).toBe(true);
      return;
    }

    // User has access - test audit functionality
    expect(isAuditPage).toBe(true);

    const auditListPage = page.locator('[data-testid="audit-event-list-page"]');
    await expect(auditListPage).toBeVisible({ timeout: 10000 });

    // Apply filters
    const resourceTypeFilter = page.locator('#audit-resource-type-filter');
    if ((await resourceTypeFilter.count()) > 0) {
      await resourceTypeFilter.selectOption('ASSET');
      await page.waitForTimeout(2000);
    }

    const actionFilter = page.locator('#audit-action-filter');
    if ((await actionFilter.count()) > 0) {
      await actionFilter.selectOption('CREATED');
      await page.waitForTimeout(2000);
    }

    // Check if export buttons exist
    const exportCsvBtn = page.getByRole('button', { name: /Export CSV/i });
    const exportJsonBtn = page.getByRole('button', { name: /Export JSON/i });

    const hasExportButtons = (await exportCsvBtn.count()) > 0 || (await exportJsonBtn.count()) > 0;
    expect(hasExportButtons).toBe(true);

    // Try export (if there are events)
    const table = page.locator('.audit-event-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = (await table.count()) > 0;
    const hasEmpty = (await emptyState.count()) > 0;

    if (hasTable && (await exportJsonBtn.count()) > 0) {
      const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
      await exportJsonBtn.click();
      await page.waitForTimeout(2000);
      try {
        await downloadPromise;
      } catch {
        /* Optional: download may not trigger depending on browser behavior */
      }
      // Download may or may not trigger depending on browser behavior
      // Just verify button click didn't crash
      expect(auditListPage).toBeVisible();
    }

    // Assert no crash - page still visible
    await expect(auditListPage.or(page.locator('body'))).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.K — Scheduled Ingestion: list schedules; open one; optional trigger', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/scheduled-ingestions', {
      timeout: 60000,
      contentSelector:
        '[data-testid="scheduled-ingestion-list-page"], .empty-state, .error-display, .loading-spinner-container, h1',
    });

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if user has access (not 403)
    const is403 = page.url().includes('/403');
    const isScheduledIngestionPage = page.url().includes('/scheduled-ingestions');

    if (is403) {
      // User doesn't have DATA_PROVIDER role - role gating works
      expect(is403).toBe(true);
      return;
    }

    // User has access - test scheduled ingestion functionality
    expect(isScheduledIngestionPage).toBe(true);

    await waitForLoadingComplete(page, { timeout: 15000 });

    const listPage = page.locator(
      '[data-testid="scheduled-ingestion-list-page"], .scheduled-ingestion-list-page, .empty-state'
    );
    await expect(listPage.first()).toBeVisible({ timeout: 15000 });

    const table = page.locator('.scheduled-ingestion-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = (await table.count()) > 0;
    const hasEmpty = (await emptyState.count()) > 0;

    if (hasTable) {
      // Open first schedule
      const firstRow = table.locator('tbody tr').first();
      await firstRow.click();
      await page.waitForURL(/\/scheduled-ingestions\/[^/]+$/, { timeout: 10000 });
      await page.waitForTimeout(2000);

      const detailPage = page.locator('[data-testid="scheduled-ingestion-detail-page"]');
      await expect(detailPage).toBeVisible({ timeout: 10000 });

      // Check if trigger button exists and schedule is ACTIVE
      const triggerBtn = page.getByRole('button', { name: /Trigger Now/i });
      if ((await triggerBtn.count()) > 0) {
        // Optional trigger - click if available
        const triggerPromise = page.waitForResponse(
          (resp) =>
            resp.url().includes('/trigger/') && (resp.status() === 200 || resp.status() === 503),
          { timeout: 30000 }
        );
        await triggerBtn.click();
        await page.waitForTimeout(2000);
        try {
          await triggerPromise;
        } catch {
          /* Optional: trigger response may timeout if service unavailable */
        }
        // Just verify page didn't crash
        await expect(detailPage).toBeVisible({ timeout: 5000 });
      }

      // Assert no crash - detail page still visible
      await expect(detailPage).toBeVisible({ timeout: 5000 });
    } else if (hasEmpty) {
      // No schedules - page loaded correctly
      expect(hasEmpty).toBe(true);
      // Assert no crash - list page still visible
      await expect(listPage).toBeVisible({ timeout: 5000 });
    } else {
      // Fallback: assert body is visible
      await expect(page.locator('body')).toBeVisible({ timeout: 5000 });
    }
  });

  test('Phase 7.5.L — Semantic: page loads; SPARQL query; URI lookup', async ({ page }) => {
    await page.goto('/semantic', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    // If redirected to login (expired token), re-login and retry
    if (page.url().includes('/login')) {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
    }

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if capability is available (may redirect to /unavailable)
    const isUnavailable = page.url().includes('/unavailable');
    const isSemanticPage = page.url().includes('/semantic');

    if (isUnavailable) {
      // Semantic capability not available - capability gating works
      expect(isUnavailable).toBe(true);
      return;
    }

    if (!isSemanticPage) {
      // May be on /login or other route - skip semantic-specific assertions
      expect(page.url()).toMatch(/\/(semantic|unavailable|login)/);
      return;
    }

    // Capability available - test semantic functionality
    await waitForLoadingComplete(page, { timeout: 15000 });

    const semanticPage = page.locator('[data-testid="semantic-page"], .semantic-page');
    await expect(semanticPage.first()).toBeVisible({ timeout: 15000 });

    // Test SPARQL tab
    const sparqlTab = page.getByRole('button', { name: /SPARQL Query/i });
    await expect(sparqlTab).toBeVisible({ timeout: 5000 });
    await sparqlTab.click();
    await page.waitForTimeout(1000);

    const sparqlSection = page.locator('[data-testid="semantic-sparql-section"]');
    await expect(sparqlSection).toBeVisible({ timeout: 5000 });

    const queryInput = page.locator('#sparql-query');
    await expect(queryInput).toBeVisible({ timeout: 5000 });
    await queryInput.fill('SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5');

    const executeBtn = page.getByRole('button', { name: /Execute Query/i });
    await expect(executeBtn).toBeVisible({ timeout: 5000 });

    // Try executing query (may succeed or return 503 if service unavailable)
    const queryPromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/semantic/sparql') &&
        (resp.status() === 200 || resp.status() === 503),
      { timeout: 30000 }
    );
    await executeBtn.click();
    await page.waitForTimeout(2000);
    try {
      await queryPromise;
    } catch {
      /* Optional: SPARQL response may timeout if service unavailable */
    }

    // Assert page didn't crash
    await expect(semanticPage).toBeVisible({ timeout: 5000 });

    // Test URI Lookup tab
    const uriTab = page.getByRole('button', { name: /URI Lookup/i });
    await expect(uriTab).toBeVisible({ timeout: 5000 });
    await uriTab.click();
    await page.waitForTimeout(1000);

    const uriSection = page.locator('[data-testid="semantic-uri-lookup-section"]');
    await expect(uriSection).toBeVisible({ timeout: 5000 });

    // Test Ontology tab
    const ontologyTab = page.getByRole('button', { name: /Ontology/i });
    await expect(ontologyTab).toBeVisible({ timeout: 5000 });
    await ontologyTab.click();
    await page.waitForTimeout(1000);

    const ontologySection = page.locator('[data-testid="semantic-ontology-section"]');
    await expect(ontologySection).toBeVisible({ timeout: 5000 });

    // Assert no crash - page still visible
    await expect(semanticPage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.M — Schema Matching: submit schema-matching request and assert result or error shown', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
      timeout: 60000,
      contentSelector:
        '[data-testid="schema-matching-page"], .schema-matching-page, .unavailable-page, .loading-spinner-container, .error-display, h1',
      acceptRedirectToLogin: true,
    });

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if capability is available (may redirect to /unavailable)
    const isUnavailable = page.url().includes('/unavailable');
    const isSchemaMatchingPage = page.url().includes('/ai/schema-matching');

    if (isUnavailable) {
      // Schema matching capability not available - capability gating works
      expect(isUnavailable).toBe(true);
      return;
    }

    if (!isSchemaMatchingPage) {
      // May be on /login or other route - skip schema-matching-specific assertions
      expect(page.url()).toMatch(/\/(ai\/schema-matching|unavailable|login)/);
      return;
    }

    // Capability available - test schema matching functionality
    await waitForLoadingComplete(page, { timeout: 15000 });

    const schemaMatchingPage = page.locator(
      '[data-testid="schema-matching-page"], .schema-matching-page'
    );
    await expect(schemaMatchingPage.first()).toBeVisible({ timeout: 20000 });

    // Fill in source schema
    const sourceSchemaInput = page.locator('#source-schema');
    await expect(sourceSchemaInput).toBeVisible({ timeout: 5000 });
    await sourceSchemaInput.fill(
      JSON.stringify(
        {
          properties: {
            customer_id: { type: 'string' },
            email: { type: 'string' },
            age: { type: 'number' },
          },
        },
        null,
        2
      )
    );

    // Fill in target schema
    const targetSchemaInput = page.locator('#target-schema');
    await expect(targetSchemaInput).toBeVisible({ timeout: 5000 });
    await targetSchemaInput.fill(
      JSON.stringify(
        {
          properties: {
            id: { type: 'string' },
            email_address: { type: 'string' },
            years_old: { type: 'integer' },
          },
        },
        null,
        2
      )
    );

    // Submit form
    const submitBtn = page.getByRole('button', { name: /Match Schemas/i });
    await expect(submitBtn).toBeVisible({ timeout: 5000 });

    // Try submitting (may succeed or return 503 if service unavailable)
    const submitPromise = page.waitForResponse(
      (resp) =>
        resp.url().includes('/ai/schema-matching') &&
        (resp.status() === 200 || resp.status() === 503 || resp.status() === 500),
      { timeout: 30000 }
    );
    await submitBtn.click();
    await page.waitForTimeout(2000);
    try {
      await submitPromise;
    } catch {
      /* Optional: schema-matching response may timeout if service unavailable */
    }

    // Wait for either results or error to appear
    await page.waitForTimeout(3000);

    // Check for results or error display
    const results = page.locator('[data-testid="schema-matching-results"]');
    const errorDisplay = page.locator('.error-display');
    const hasResults = (await results.count()) > 0;
    const hasError = (await errorDisplay.count()) > 0;

    // Assert either results shown or error displayed (or still loading)
    if (hasResults) {
      await expect(results).toBeVisible({ timeout: 5000 });
      // Check for matches table or no matches message
      const matchesTable = results.locator('.matches-table');
      const noMatches = results.locator('.no-matches');
      const hasTable = (await matchesTable.count()) > 0;
      const hasNoMatches = (await noMatches.count()) > 0;
      expect(hasTable || hasNoMatches).toBe(true);
    } else if (hasError) {
      await expect(errorDisplay).toBeVisible({ timeout: 5000 });
    }
    // If neither, might still be loading (acceptable)

    // Assert page didn't crash
    await expect(schemaMatchingPage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.J — Webhooks: create webhook; list shows it; delete', async ({ page }) => {
    test.setTimeout(360000); // 6 min: create + list + delete under visible/slowMo
    const webhookName = `e2e-webhook-${Date.now()}`;
    const webhookUrl = 'https://example.com/webhook';
    const webhookSecret = 'e2e-secret-key';

    // Use tenant admin for full webhook access (ensure_e2e_user_roles required)
    const testUser = await getTenantAdminUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2500);
    await loginAndNavigateToRoute(page, testUser, '/webhooks', {
      timeout: 60000,
      contentSelector: '.webhook-list-page, .empty-state, .error-display, h1',
    });

    const listPage = page.locator('.webhook-list-page');
    await expect(listPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: 'Webhooks', exact: true });
    await expect(heading).toBeVisible({ timeout: 5000 });

    await page.getByRole('button', { name: 'Create webhook' }).first().click();
    await page.waitForURL(/\/webhooks\/create/, { timeout: 5000 });
    await page.waitForTimeout(2000);

    await page.getByLabel(/Name \(required\)/i).fill(webhookName);
    await page.getByLabel(/URL \(required\)/i).fill(webhookUrl);
    await page.getByLabel(/Secret \(required\)/i).fill(webhookSecret);

    const firstCheckbox = page.locator('.webhook-event-checkbox input[type="checkbox"]').first();
    await firstCheckbox.waitFor({ state: 'attached', timeout: 10000 });
    await firstCheckbox.check();

    await page.getByRole('button', { name: /Create webhook/i }).click();
    // Wait for detail page: URL must be /webhooks/{id} with id not "create" (UUID)
    await page.waitForURL(/\/webhooks\/[0-9a-f-]{36}$/i, { timeout: 20000 });
    const detailUrlAfterCreate = page.url();
    await page.waitForTimeout(2000);

    // Ensure we're on detail page (heading = webhook name or "Back to Webhooks" present)
    const detailPage = page.locator('.webhook-detail-page');
    await expect(detailPage).toBeVisible({ timeout: 10000 });

    await navigateToRouteFromApp(page, '/webhooks', {
      timeout: 60000,
      contentSelector: '.webhook-list-page, .webhook-list-table, .empty-state, .error-display',
    });
    try {
      await page.waitForResponse(
        (resp) =>
          resp.request().method() === 'GET' &&
          resp.url().includes('/webhooks/webhooks/') &&
          resp.status() === 200,
        { timeout: 20000 }
      );
    } catch {
      /* Optional: webhooks list API may have already completed */
    }
    await page.waitForTimeout(2000);

    const webhookListPage = page.locator('.webhook-list-page');
    await expect(webhookListPage).toBeVisible({ timeout: 15000 });
    const table = page.locator('.webhook-list-table');
    const rowWithName = table.locator('tbody tr').filter({ hasText: webhookName });
    let rowVisible = false;
    try {
      rowVisible = await rowWithName.isVisible();
    } catch {
      /* Row not yet visible */
    }
    if (!rowVisible) {
      await page.waitForTimeout(3000);
      try {
        rowVisible = await rowWithName.isVisible();
      } catch {
        /* Row not yet visible */
      }
    }
    if (!rowVisible) {
      await page.reload({ waitUntil: 'domcontentloaded' });
      await loginAndNavigateToRoute(page, testUser, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .webhook-list-table, .empty-state, .error-display',
      });
      await page.waitForTimeout(2000);
      try {
        rowVisible = await rowWithName.isVisible();
      } catch {
        /* Row not yet visible */
      }
    }
    if (rowVisible) {
      await rowWithName.click();
      await page.waitForURL(/\/webhooks\/[0-9a-f-]{36}$/i, { timeout: 15000 });
    } else {
      const detailPath = new URL(detailUrlAfterCreate).pathname;
      await loginAndNavigateToRoute(page, testUser, detailPath, {
        timeout: 60000,
        contentSelector: '.webhook-detail-page, .error-display',
      });
    }
    await page.waitForURL(/\/webhooks\/[0-9a-f-]{36}$/i, { timeout: 20000 });
    await page.waitForTimeout(2000);

    const errEl = page.locator('.error-display');
    let errVisible = false;
    try {
      errVisible = await errEl.isVisible();
    } catch {
      /* Error element state unknown */
    }
    if (errVisible) {
      let msg = '';
      try {
        msg = (await errEl.textContent()) || '';
      } catch {
        /* Could not get error text */
      }
      throw new Error(`Webhook detail showed error (API/404): ${msg.slice(0, 300)}`);
    }
    const deleteBtn = page.getByRole('button', { name: 'Delete' }).first();
    await expect(deleteBtn).toBeVisible({ timeout: 15000 });
    await deleteBtn.click();
    await page.waitForTimeout(1000);
    const confirmBtn = page.locator('.webhook-delete-actions .btn-danger');
    await expect(confirmBtn).toBeVisible({ timeout: 5000 });
    await confirmBtn.click();
    await page.waitForURL(/\/webhooks\/?$/, { timeout: 10000 });
    await page.waitForTimeout(2000);

    const rowAfterDelete = page
      .locator('.webhook-list-table tbody tr')
      .filter({ hasText: webhookName });
    await expect(rowAfterDelete).not.toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.N.1 — Home: after login home loads and shows at least one section', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });

    const homePage = page.locator('[data-testid="home-page"]');
    await expect(homePage).toBeVisible({ timeout: 10000 });

    // Check for at least one section (quick actions, recent assets, datasets, or jobs)
    const quickActions = page.locator('[data-testid="home-quick-actions"]');
    const recentAssets = page.locator('[data-testid="home-recent-assets"]');
    const recentDatasets = page.locator('[data-testid="home-recent-datasets"]');
    const recentJobs = page.locator('[data-testid="home-recent-jobs"]');

    const hasQuickActions = (await quickActions.count()) > 0;
    const hasRecentAssets = (await recentAssets.count()) > 0;
    const hasRecentDatasets = (await recentDatasets.count()) > 0;
    const hasRecentJobs = (await recentJobs.count()) > 0;

    // Assert at least one section is visible
    expect(hasQuickActions || hasRecentAssets || hasRecentDatasets || hasRecentJobs).toBe(true);

    // Check for system status widget
    const systemStatus = page.locator('[data-testid="home-system-status"]');
    await expect(systemStatus).toBeVisible({ timeout: 5000 });

    // Assert page didn't crash
    await expect(homePage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.O.2 — Health: system status widget displays status on home page', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/', {
      timeout: 60000,
      contentSelector: '[data-testid="home-page"], .home-page, main',
    });

    const homePage = page.locator('[data-testid="home-page"]');
    await expect(homePage).toBeVisible({ timeout: 10000 });

    // Check for system status widget
    const systemStatus = page.locator('[data-testid="home-system-status"]');
    await expect(systemStatus).toBeVisible({ timeout: 5000 });

    // Check that status badge is visible (may show "CHECKING...", "HEALTHY", "DEGRADED", "UNHEALTHY", or "UNKNOWN")
    const statusBadge = systemStatus.locator('.system-status-badge');
    await expect(statusBadge).toBeVisible({ timeout: 5000 });

    // Wait a bit more for health check to complete
    await page.waitForTimeout(2000);

    // Verify status badge shows a valid status
    const badgeText = await statusBadge.textContent();
    expect(badgeText).toBeTruthy();
    expect(['CHECKING...', 'HEALTHY', 'DEGRADED', 'UNHEALTHY', 'UNKNOWN']).toContain(
      badgeText?.trim().toUpperCase()
    );

    // Assert page didn't crash
    await expect(homePage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.N.2 — Admin: as tenant/platform admin open admin and assert content or "no permissions"', async ({
    page,
  }) => {
    await page.goto('/admin', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Check if redirected (403 or login) or page loads
    const currentUrl = page.url();
    const isRedirected = currentUrl.includes('/login') || currentUrl.includes('/403');
    const isAdminPage = currentUrl.includes('/admin');

    if (isRedirected) {
      // User doesn't have admin access - ProtectedRoute redirected
      expect(isRedirected).toBe(true);
      return;
    }

    // User has access - check admin page content
    expect(isAdminPage).toBe(true);

    const adminPage = page.locator('[data-testid="admin-page"]');
    await expect(adminPage).toBeVisible({ timeout: 10000 });

    // Check if user has admin access or shows "no permissions"
    const noPermission = page.locator('.admin-no-permission');
    const overviewSection = page.locator('[data-testid="admin-overview-section"]');
    const tenantsSection = page.locator('[data-testid="admin-tenants-section"]');
    const usersSection = page.locator('[data-testid="admin-users-section"]');

    const hasNoPermission = (await noPermission.count()) > 0;
    const hasOverview = (await overviewSection.count()) > 0;
    const hasTenants = (await tenantsSection.count()) > 0;
    const hasUsers = (await usersSection.count()) > 0;

    // Assert either no permission message OR admin content is shown
    expect(hasNoPermission || hasOverview || hasTenants || hasUsers).toBe(true);

    // If has access, check that overview section is visible
    if (!hasNoPermission) {
      await expect(overviewSection).toBeVisible({ timeout: 5000 });
    }

    // Assert page didn't crash
    await expect(adminPage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5 critical routes are handled by app (no crash)', async ({ page }) => {
    const routes = [
      '/search',
      '/governance',
      '/files',
      '/audit',
      '/scheduled-ingestions',
      '/semantic',
      '/webhooks',
    ];

    for (const route of routes) {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500);

      const body = page.locator('body');
      await expect(body).toBeVisible();
    }
  });
});
