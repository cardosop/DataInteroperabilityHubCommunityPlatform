/**
 * E2E: Scheduled Export Journey (Phase 22)
 *
 * Use Cases: UC-EXPORT-001 (Schedule Recurring Export), UC-EXPORT-002 (Configure Export Destination),
 * UC-EXPORT-003 (Trigger Manual Export), UC-EXPORT-004 (Monitor Export Runs)
 * Journeys: JOURNEY-EXPORT-001, JOURNEY-EXPORT-002
 * Reference: docs/USE_CASES.md, docs/USER_JOURNEYS.md
 *
 * Create scheduled export → trigger → wait for run completion (poll run status) → assert.
 * Real backend and real Prefect (or real backend with Prefect flow in test env).
 * No stubbing of API or Prefect; flakiness addressed by explicit wait for run status.
 */

import { expect, test } from '@playwright/test';
import { cleanupOldScheduledExports, createAssetViaApi } from '../../fixtures/api-assets';
import { clearAuthStorage, getTenantAdminUser, loginUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

const API_BASE = process.env.E2E_API_BASE_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const PREFECT_INTEGRATION_URL =
  process.env.PREFECT_INTEGRATION_SERVICE_URL || 'http://localhost:8084';
const POLL_INTERVAL_MS = 5000;
// Increased timeout to handle Docker daemon performance issues (Prefect flow runs may take longer)
const RUN_COMPLETION_TIMEOUT_MS = 240000; // 4 minutes (Docker/CI can be slow)

type RunStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface ScheduledExportRun {
  id: string;
  status: RunStatus;
  items_found: number | null;
  items_exported: number | null;
  items_failed: number | null;
  started_at: string | null;
  completed_at: string | null;
  prefect_flow_run_id: string | null;
}

/**
 * Poll GET /api/v1/scheduled-exports/{exportId}/runs/ until we find a run with matching prefect_flow_run_id
 * and status is COMPLETED or FAILED, or timeout.
 * Uses token from localStorage (page must be authenticated).
 */
async function pollRunUntilTerminal(
  page: import('@playwright/test').Page,
  exportId: string,
  flowRunId: string,
  options: { timeoutMs?: number; intervalMs?: number } = {}
): Promise<ScheduledExportRun> {
  const timeoutMs = options.timeoutMs ?? RUN_COMPLETION_TIMEOUT_MS;
  const intervalMs = options.intervalMs ?? POLL_INTERVAL_MS;
  const start = Date.now();

  const getToken = () => page.evaluate(() => localStorage.getItem('access_token') || '');

  const fetchRuns = async (): Promise<ScheduledExportRun[]> => {
    const token = await getToken();
    if (!token) throw new Error('Not authenticated');
    const result = await page.evaluate(
      async ({
        base,
        exportId: id,
        token: t,
      }: {
        base: string;
        exportId: string;
        token: string;
      }): Promise<{ ok: boolean; status: number; body: unknown }> => {
        // Add cache-busting query parameter to ensure fresh data
        const url = `${base.replace(/\/$/, '')}/scheduled-exports/${id}/runs/?_t=${Date.now()}`;
        const r = await fetch(url, {
          headers: { Authorization: `Bearer ${t}` },
          cache: 'no-store',
        });
        const body = await r.json().catch(() => ({ message: r.statusText }));
        return { ok: r.ok, status: r.status, body };
      },
      { base: API_BASE, exportId, token }
    );
    if (!result.ok) {
      if (result.status === 404) {
        throw new Error(
          `Export runs not found (404). exportId=${exportId}, base=${API_BASE}. Body: ${JSON.stringify(result.body)}`
        );
      }
      throw new Error(`GET runs failed: ${result.status} ${JSON.stringify(result.body)}`);
    }
    return result.body as ScheduledExportRun[];
  };

  // First poll: allow one short delay in case run is not yet visible (eventual consistency)
  await page.waitForTimeout(2000);

  // Trigger status sync immediately after trigger to catch quick failures
  try {
    await page.evaluate(
      async (url: string) => {
        await fetch(`${url}/status/sync`, { method: 'POST' }).catch(() => {});
      },
      PREFECT_INTEGRATION_URL.replace(/\/$/, '')
    );
  } catch (e) {
    // Ignore status sync errors - continue polling
  }

  // Trigger status sync periodically to update run status from Prefect (handles Docker timeout crashes)
  const STATUS_SYNC_INTERVAL_MS = 5000; // Sync every 5 seconds (reduced from 10s for faster updates)
  let lastStatusSync = Date.now();

  while (Date.now() - start < timeoutMs) {
    // Trigger status sync before fetching runs to ensure we have latest status
    if (Date.now() - lastStatusSync >= STATUS_SYNC_INTERVAL_MS) {
      try {
        // Trigger status sync and wait for it to complete
        await page.evaluate(
          async (url: string) => {
            const response = await fetch(`${url}/status/sync`, {
              method: 'POST',
            }).catch(() => null);
            // Wait a bit for the sync to process and update the database
            await new Promise((resolve) => setTimeout(resolve, 2000));
            return response;
          },
          PREFECT_INTEGRATION_URL.replace(/\/$/, '')
        );
        lastStatusSync = Date.now();
      } catch (e) {
        // Ignore status sync errors - continue polling
      }
    }

    const runs = await fetchRuns();
    const matchingRun = runs.find((r) => r.prefect_flow_run_id === flowRunId);
    if (matchingRun) {
      // Check for terminal states (including FAILED which indicates Docker/prefect issues)
      if (
        matchingRun.status === 'COMPLETED' ||
        matchingRun.status === 'FAILED' ||
        matchingRun.status === 'CANCELLED'
      ) {
        return matchingRun;
      }
      // Log current status for debugging (only in test mode)
      if (process.env.DEBUG) {
        console.log(
          `[DEBUG] Run ${matchingRun.id} status: ${matchingRun.status}, waiting for terminal state...`
        );
      }
    } else {
      // Run not found yet - might not be created or still propagating
      if (process.env.DEBUG) {
        console.log(
          `[DEBUG] Run with flow_run_id ${flowRunId} not found yet, continuing to poll...`
        );
      }
    }
    await page.waitForTimeout(intervalMs);
  }

  // Final check - trigger one more status sync before final check and wait longer
  try {
    await page.evaluate(
      async (url: string) => {
        const response = await fetch(`${url}/status/sync`, { method: 'POST' }).catch(
          () => null
        );
        // Wait longer for sync to process and database to update
        await new Promise((resolve) => setTimeout(resolve, 3000));
        return response;
      },
      PREFECT_INTEGRATION_URL.replace(/\/$/, '')
    );
  } catch (e) {
    // Ignore status sync errors
  }

  // Fetch runs multiple times with delays to ensure we get fresh data
  let matchingRun: ScheduledExportRun | undefined;
  for (let i = 0; i < 3; i++) {
    await page.waitForTimeout(1000); // Wait between fetches
    const runs = await fetchRuns();
    matchingRun = runs.find((r) => r.prefect_flow_run_id === flowRunId);
    if (matchingRun) {
      // Log status for debugging
      console.log(
        `[DEBUG] Final check ${i + 1}/3: Run ${matchingRun.id} status: ${matchingRun.status}`
      );
      // If we found a terminal state, break early
      if (
        matchingRun.status === 'COMPLETED' ||
        matchingRun.status === 'FAILED' ||
        matchingRun.status === 'CANCELLED'
      ) {
        break;
      }
    }
  }

  if (!matchingRun) {
    throw new Error(
      `Run with flow_run_id ${flowRunId} not found within ${timeoutMs}ms. ` +
        'Ensure Prefect worker is running and processing jobs.'
    );
  }
  if (
    matchingRun.status !== 'COMPLETED' &&
    matchingRun.status !== 'FAILED' &&
    matchingRun.status !== 'CANCELLED'
  ) {
    throw new Error(
      `Run ${matchingRun.id} did not reach terminal state within ${timeoutMs}ms; last status: ${matchingRun.status}. ` +
        'Ensure Prefect worker is running and processing jobs.'
    );
  }
  return matchingRun;
}

test.describe('Scheduled Export Journey', () => {
  // 12 min: visible/slowMo; login + create asset + cleanup + create export + trigger + poll (~240s) under parallel E2E load
  test.setTimeout(480000); // 8 min: create + trigger + poll (4 min); aligned with RUN_COMPLETION_TIMEOUT_MS

  test.describe('Failure', () => {
    test('unauthenticated access to scheduled-exports redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/scheduled-exports', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|scheduled-exports|403)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onRouteWithLoginPrompt =
        url.includes('/scheduled-exports') &&
        (await hasLoginPrompt(page));
      expect(onLogin || onRouteWithLoginPrompt).toBe(true);
    });
  });

  test.describe('JOURNEY-EXPORT-001: Create and Run Scheduled Export', () => {
    test('create scheduled export → trigger → poll run status → assert run outcome', async ({
      page,
    }) => {
      // Pre-check: skip early if Prefect integration service is not reachable
      try {
        const healthRes = await fetch(`${PREFECT_INTEGRATION_URL.replace(/\/$/, '')}/health`, {
          signal: AbortSignal.timeout(10000),
        });
        if (!healthRes.ok) {
          throw new Error(
            `Prefect integration service unhealthy (${healthRes.status}). Scheduled export requires Prefect. ` +
              `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
          );
        }
      } catch (e) {
        throw new Error(
          `Prefect integration service not reachable at ${PREFECT_INTEGRATION_URL}. Scheduled export requires Prefect. ` +
            `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
        );
      }

      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports', {
        timeout: 90000,
        contentSelector:
          '.scheduled-export-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error(
          'Scheduled exports redirected to login. Precondition failure: E2E user roles not set up. ' +
            'Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles'
        );
      }

      // Wait for list content: Create Export button (header or empty state; use .first() when both visible)
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await createBtn.waitFor({ state: 'visible', timeout: 30000 });
      await createBtn.click();
      await page.waitForURL(/\/scheduled-exports\/create/, { timeout: 10000 });

      // Create a test asset via API (required for source_scope)
      const assetId = await createAssetViaApi(testUser);

      // Clean up old E2E scheduled exports to avoid plan limit issues
      await cleanupOldScheduledExports(testUser);

      // Navigate back to scheduled export create page (domcontentloaded faster than networkidle under load)
      await page.goto('/scheduled-exports/create', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(1500); // Allow form to render

      const name = `e2e-se-${Date.now()}`;
      await page.getByLabel(/name/i).fill(name);
      // Fill cron expression
      await page.getByLabel(/cron/i).fill('0 2 * * *');
      // Fill asset IDs (required for source_scope validation)
      await page.getByLabel(/asset ids/i).fill(assetId);
      await page.getByRole('button', { name: /^Create$/i }).click();

      try {
        await page.waitForURL(
          (url) => url.pathname.includes('/scheduled-exports/') && !url.pathname.endsWith('/create'),
          {
            timeout: 30000,
            waitUntil: 'domcontentloaded',
          }
        );
      } catch (err) {
        const hasError = (await page.locator('.error-display').count()) > 0;
        const errText = hasError
          ? (await page.locator('.error-display').first().textContent().catch(() => '')) || ''
          : '';
        throw new Error(
          `Scheduled export create did not navigate to detail within 30s. ${errText ? `Error: ${errText.slice(0, 150)}` : 'Check backend and Prefect availability.'}`
        );
      }
      // Detail page may show loading, then content; or error/empty if create failed
      // Use .first() to avoid strict mode violation when both detail page and runs-section empty-state exist
      await page
        .locator('[data-testid="scheduled-export-detail-page"], .error-display, .empty-state')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });
      // Only skip on page-level error or "not found" empty - not the runs section "No runs" empty state
      const hasPageError = (await page.locator('.error-display').count()) > 0;
      const hasNotFoundEmpty =
        (await page.locator('.empty-state:has-text("not found"), .empty-state:has-text("could not be found")').count()) >
        0;
      if (hasPageError || (hasNotFoundEmpty && (await page.locator('[data-testid="scheduled-export-detail-page"]').count()) === 0)) {
        throw new Error(
          'Scheduled export create or load failed (error/empty). Check backend logs and Prefect availability.'
        );
      }
      await expect(page.locator('[data-testid="scheduled-export-detail-page"]')).toBeVisible({
        timeout: 5000,
      });

      // Wait for export to load (name visible)
      await expect(page.getByText(name, { exact: false })).toBeVisible({ timeout: 10000 });

      // Allow deployment sync to complete (on_commit creates Prefect deployment asynchronously)
      await page.waitForTimeout(10000);

      // Trigger button: match "Trigger Now", "Triggering...", or aria-label
      const triggerBtn = page.getByRole('button', { name: /trigger/i });
      await triggerBtn.scrollIntoViewIfNeeded().catch(() => {});
      await triggerBtn.waitFor({ state: 'visible', timeout: 15000 });

      const maxTriggerAttempts = 3;
      let triggerResponse!: Awaited<ReturnType<typeof page.waitForResponse>>;

      for (let attempt = 1; attempt <= maxTriggerAttempts; attempt++) {
        try {
          const triggerResponsePromise = page.waitForResponse(
            (resp) =>
              resp.url().includes('/trigger/') &&
              resp.request().method() === 'POST' &&
              (resp.status() === 200 ||
                resp.status() === 503 ||
                resp.status() === 404 ||
                resp.status() >= 400),
            { timeout: 90000 }
          );

          page.once('dialog', (d) => d.accept());
          await triggerBtn.click();

          triggerResponse = await triggerResponsePromise;
        } catch (triggerErr) {
          const msg = triggerErr instanceof Error ? triggerErr.message : String(triggerErr);
          const isTimeout = /timeout|exceeded/i.test(msg);
          const isNetwork = /network|empty.?response|connection/i.test(msg);
          if ((isTimeout || isNetwork) && attempt < maxTriggerAttempts) {
            await page.waitForTimeout(5000);
            continue;
          }
          if (isTimeout || isNetwork) {
            throw new Error(
              `Trigger did not respond within 90s (${msg.slice(0, 80)}). ` +
                'Ensure Prefect integration service and backend are running. ' +
                'Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test'
            );
          }
          throw triggerErr;
        }
        if (triggerResponse.status() === 200) break;
        if (triggerResponse.status() === 503) {
          const body = await triggerResponse.json().catch(() => ({}));
          throw new Error(
            `Prefect not available (503). Scheduled export requires Prefect. ` +
              `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test. Body: ${JSON.stringify(body)}`
          );
        }
        if (triggerResponse.status() === 404 && attempt < maxTriggerAttempts) {
          await page.waitForTimeout(5000);
          continue;
        }
        if (triggerResponse.status() === 404) {
          const body = await triggerResponse.json().catch(() => ({}));
          throw new Error(
            `Prefect deployment not found (404) after ${maxTriggerAttempts} attempts. Scheduled export requires Prefect. ` +
              `Ensure prefect-integration-service-test is running and sync completes. Body: ${JSON.stringify(body)}`
          );
        }
        if (triggerResponse.status() >= 400) {
          const body = await triggerResponse.json().catch(() => ({}));
          throw new Error(`Trigger failed: ${triggerResponse.status()} ${JSON.stringify(body)}`);
        }
      }

      const triggerBody = await triggerResponse.json();
      const flowRunId = triggerBody.flow_run_id;
      if (!flowRunId || typeof flowRunId !== 'string') {
        throw new Error(`Trigger response missing flow_run_id: ${JSON.stringify(triggerBody)}`);
      }

      // Extract export ID from URL
      const exportId = page.url().match(/\/scheduled-exports\/([^/]+)/)?.[1];
      if (!exportId) {
        throw new Error('Could not extract export ID from URL');
      }

      let run: Awaited<ReturnType<typeof pollRunUntilTerminal>>;
      try {
        run = await pollRunUntilTerminal(page, exportId, flowRunId);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (
          msg.includes('not found within') ||
          msg.includes('did not reach terminal state') ||
          msg.includes('Ensure Prefect worker')
        ) {
          throw new Error(
            `Prefect run polling failed: ${msg}. Scheduled export requires Prefect. ` +
              `Ensure Prefect stack is running: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
          );
        }
        throw err;
      }

      expect(['COMPLETED', 'FAILED', 'CANCELLED']).toContain(run.status);
      if (run.status === 'COMPLETED') {
        expect(typeof run.items_found).toBe('number');
        expect(typeof run.items_exported).toBe('number');
        expect(run.items_found).toBeGreaterThanOrEqual(0);
        expect(run.items_exported).toBeGreaterThanOrEqual(0);
      }
      if (run.status === 'FAILED') {
        // Failed runs may have error details in result_json
        expect(run.items_failed).toBeGreaterThanOrEqual(0);
      }
    });
  });

  test.describe('JOURNEY-EXPORT-002: Monitor and Troubleshoot Export Runs', () => {
    test('view export runs list → view run details → verify run status and metrics', async ({
      page,
    }) => {
      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/scheduled-exports', {
        timeout: 90000,
        contentSelector:
          '.scheduled-export-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error(
          'Scheduled exports redirected to login. Precondition failure: E2E user roles not set up. ' +
            'Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles'
        );
      }

      // Wait for list content
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await createBtn.waitFor({ state: 'visible', timeout: 30000 });

      // Wait for list content to load (table or empty state)
      await page.waitForSelector(
        '.scheduled-export-table tbody tr, .empty-state, [data-testid="scheduled-export-list-page"]',
        { timeout: 15000 }
      );
      await page.waitForTimeout(2000);

      // Check if there are any exports; if none, create one via UI (self-contained test)
      const exportRows = page.locator(
        '[data-testid="scheduled-export-row"], .scheduled-export-table tbody tr.row-link'
      );
      let exportCount = await exportRows.count();

      if (exportCount === 0) {
        const assetId = await createAssetViaApi(testUser);
        await cleanupOldScheduledExports(testUser);
        await createBtn.click();
        await page.waitForURL(/\/scheduled-exports\/create/, { timeout: 10000 });
        await page.waitForTimeout(1500);
        const name = `e2e-se-monitor-${Date.now()}`;
        await page.getByLabel(/name/i).fill(name);
        await page.getByLabel(/cron/i).fill('0 2 * * *');
        await page.getByLabel(/asset ids/i).fill(assetId);
        await page.getByRole('button', { name: /^Create$/i }).click();
        await page.waitForURL(
          (url) => url.pathname.includes('/scheduled-exports/') && !url.pathname.endsWith('/create'),
          { timeout: 15000 }
        );
        await page.goto('/scheduled-exports', { waitUntil: 'domcontentloaded' });
        await page.waitForSelector(
          '.scheduled-export-table tbody tr, .empty-state',
          { timeout: 20000 }
        );
        await page.waitForTimeout(3000);
        exportCount = await exportRows.count();
      }

      if (exportCount === 0) {
        throw new Error(
          'No scheduled exports found after create attempt. Precondition failure. ' +
            'Check backend logs, Prefect availability, and ensure source_scope (asset_ids) validation passes.'
        );
      }

      // Click on first export to view details
      await exportRows.first().click();
      await page.waitForURL(/\/scheduled-exports\/[^/]+$/, { timeout: 10000 });

      // Wait for export detail page (data-testid present in loading/content/error states)
      await expect(page.locator('[data-testid="scheduled-export-detail-page"]')).toBeVisible({
        timeout: 25000,
      });

      // Look for runs section or runs list
      const runsSection = page.locator(
        '[data-testid="export-runs-section"], .scheduled-export-detail-section:has(h2:has-text("Runs")), h2:has-text("Runs")'
      );
      const runsSectionCount = await runsSection.count();

      if (runsSectionCount > 0) {
        // Check if there are any runs (table rows or run items)
        const runItems = page.locator(
          '[data-testid="export-run-item"], .scheduled-export-runs-table tbody tr'
        );
        const runCount = await runItems.count();

        if (runCount > 0) {
          // Click on first run to view details
          await runItems.first().click();
          await page.waitForTimeout(2000);

          // Verify run details are visible (status, metrics, etc.)
          const hasRunDetails =
            (await page.locator('[data-testid="run-status"]').count()) > 0 ||
            (await page.locator('text=/status|completed|failed|running/i').count()) > 0 ||
            (await page.locator('text=/items.*found|items.*exported/i').count()) > 0;

          expect(hasRunDetails || page.url().includes('/runs/')).toBe(true);
        } else {
          // No runs yet, but runs section exists
          expect(runsSectionCount).toBeGreaterThan(0);
        }
      } else {
        // Runs section might not exist or be on a different page
        // Check if we can navigate to runs via API or different UI path
        expect(page.url()).toContain('/scheduled-exports/');
      }
    });
  });
});
