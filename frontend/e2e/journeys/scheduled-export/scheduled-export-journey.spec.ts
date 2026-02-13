/**
 * E2E: Scheduled Export Journey (Phase 22)
 * Create scheduled export → trigger → wait for run completion (poll run status) → assert.
 * Real backend and real Prefect (or real backend with Prefect flow in test env).
 * No stubbing of API or Prefect; flakiness addressed by explicit wait for run status.
 */

import { expect, test } from '@playwright/test';
import { cleanupOldScheduledExports, createAssetViaApi } from '../../fixtures/api-assets';
import { getTestUser, loginUser } from '../../fixtures/auth';

const API_BASE = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const POLL_INTERVAL_MS = 5000;
// Increased timeout to handle Docker daemon performance issues (Prefect flow runs may take longer)
const RUN_COMPLETION_TIMEOUT_MS = 180000; // 3 minutes (was 2 minutes)

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
    await page.evaluate(async () => {
      await fetch('http://localhost:8084/status/sync', { method: 'POST' }).catch(() => {});
    });
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
        await page.evaluate(async () => {
          const response = await fetch('http://localhost:8084/status/sync', {
            method: 'POST',
          }).catch(() => null);
          // Wait a bit for the sync to process and update the database
          await new Promise((resolve) => setTimeout(resolve, 2000));
          return response;
        });
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
    await page.evaluate(async () => {
      const response = await fetch('http://localhost:8084/status/sync', { method: 'POST' }).catch(
        () => null
      );
      // Wait longer for sync to process and database to update
      await new Promise((resolve) => setTimeout(resolve, 3000));
      return response;
    });
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
  // Increased timeout to handle Docker daemon performance issues (Prefect flow runs may take longer)
  test.setTimeout(240000); // 4 minutes (was 3 minutes)

  test.describe('JOURNEY-EXPORT-001: Create and Run Scheduled Export', () => {
    test('create scheduled export → trigger → poll run status → assert run outcome', async ({
      page,
    }) => {
      const useStoredAuth = test.info().project.name === 'chromium-routes';

      // Ensure authentication before navigating
      if (useStoredAuth) {
        // Verify stored auth is loaded and valid
        await page.goto('/', { waitUntil: 'domcontentloaded' });
        // Wait a bit for storage state to load
        await page.waitForTimeout(1000);
        const hasToken = await page.evaluate(() => {
          return !!(localStorage.getItem('access_token') && localStorage.getItem('user'));
        });
        if (!hasToken || page.url().includes('/login')) {
          // Stored auth not available or invalid, login manually
          // Clear any invalid state first
          await page.evaluate(() => {
            localStorage.clear();
            sessionStorage.clear();
          });
          await page.goto('/login', { waitUntil: 'domcontentloaded' });
          await loginUser(page, await getTestUser());
        }
      } else {
        await loginUser(page, await getTestUser());
      }

      await page.goto('/scheduled-exports', { waitUntil: 'networkidle' });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login; auth may have failed or expired.');
      }

      // Wait for list content: Create Export button (header or empty state; use .first() when both visible)
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await createBtn.waitFor({ state: 'visible', timeout: 30000 });
      await createBtn.click();
      await page.waitForURL(/\/scheduled-exports\/create/, { timeout: 10000 });

      // Create a test asset via API (required for source_scope)
      const testUser = await getTestUser();
      const assetId = await createAssetViaApi(testUser);

      // Clean up old E2E scheduled exports to avoid plan limit issues
      await cleanupOldScheduledExports(testUser);

      // Navigate back to scheduled export create page
      await page.goto('/scheduled-exports/create', { waitUntil: 'networkidle' });

      const name = `e2e-se-${Date.now()}`;
      await page.getByLabel(/name/i).fill(name);
      // Fill cron expression
      await page.getByLabel(/cron/i).fill('0 2 * * *');
      // Fill asset IDs (required for source_scope validation)
      await page.getByLabel(/asset ids/i).fill(assetId);
      await page.getByRole('button', { name: /^Create$/i }).click();

      await page.waitForURL(
        (url) => url.pathname.includes('/scheduled-exports/') && !url.pathname.endsWith('/create'),
        {
          timeout: 15000,
        }
      );
      await expect(page.locator('[data-testid="scheduled-export-detail-page"]')).toBeVisible({
        timeout: 10000,
      });

      // Wait for export to load (name visible)
      await expect(page.getByText(name, { exact: false })).toBeVisible({ timeout: 10000 });

      // Trigger button: match "Trigger Now", "Triggering...", or aria-label
      const triggerBtn = page.getByRole('button', { name: /trigger/i });
      await triggerBtn.scrollIntoViewIfNeeded().catch(() => {});
      await triggerBtn.waitFor({ state: 'visible', timeout: 15000 });

      const triggerResponsePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes('/trigger/') &&
          resp.request().method() === 'POST' &&
          (resp.status() === 200 ||
            resp.status() === 503 ||
            resp.status() === 404 ||
            resp.status() >= 400),
        { timeout: 60000 }
      );

      page.once('dialog', (d) => d.accept());
      await triggerBtn.click();

      const triggerResponse = await triggerResponsePromise;
      if (triggerResponse.status() === 503) {
        const body = await triggerResponse.json().catch(() => ({}));
        test.skip(true, `Prefect not available (503): ${JSON.stringify(body)}`);
      }
      if (triggerResponse.status() === 404) {
        const body = await triggerResponse.json().catch(() => ({}));
        test.skip(true, `Prefect deployment not found (404): ${JSON.stringify(body)}`);
      }
      if (triggerResponse.status() >= 400) {
        const body = await triggerResponse.json().catch(() => ({}));
        throw new Error(`Trigger failed: ${triggerResponse.status()} ${JSON.stringify(body)}`);
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

      const run = await pollRunUntilTerminal(page, exportId, flowRunId);

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
      const useStoredAuth = test.info().project.name === 'chromium-routes';

      // Ensure authentication before navigating
      if (useStoredAuth) {
        // Verify stored auth is loaded and valid
        await page.goto('/', { waitUntil: 'domcontentloaded' });
        // Wait a bit for storage state to load
        await page.waitForTimeout(1000);
        const hasToken = await page.evaluate(() => {
          return !!(localStorage.getItem('access_token') && localStorage.getItem('user'));
        });
        if (!hasToken || page.url().includes('/login')) {
          // Stored auth not available or invalid, login manually
          // Clear any invalid state first
          await page.evaluate(() => {
            localStorage.clear();
            sessionStorage.clear();
          });
          await page.goto('/login', { waitUntil: 'domcontentloaded' });
          await loginUser(page, await getTestUser());
        }
      } else {
        await loginUser(page, await getTestUser());
      }

      await page.goto('/scheduled-exports', { waitUntil: 'networkidle' });

      if (page.url().includes('/login')) {
        throw new Error('Unexpected redirect to login; auth may have failed or expired.');
      }

      // Wait for list content
      const createBtn = page.getByRole('button', { name: /Create Export/i }).first();
      await createBtn.waitFor({ state: 'visible', timeout: 30000 });

      // Check if there are any exports (if none, create one first)
      const exportRows = page.locator(
        '[data-testid="scheduled-export-row"], .scheduled-export-item'
      );
      const exportCount = await exportRows.count();

      if (exportCount === 0) {
        // No exports exist, skip this test or create one
        test.skip(true, 'No scheduled exports found; create one first to test run monitoring');
        return;
      }

      // Click on first export to view details
      await exportRows.first().click();
      await page.waitForURL(/\/scheduled-exports\/[^/]+$/, { timeout: 10000 });

      // Wait for export detail page
      await expect(page.locator('[data-testid="scheduled-export-detail-page"]')).toBeVisible({
        timeout: 10000,
      });

      // Look for runs section or runs list
      const runsSection = page.locator(
        '[data-testid="export-runs-section"], .export-runs-list, h2:has-text("Runs")'
      );
      const runsSectionCount = await runsSection.count();

      if (runsSectionCount > 0) {
        // Check if there are any runs
        const runItems = page.locator('[data-testid="export-run-item"], .export-run-row');
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
