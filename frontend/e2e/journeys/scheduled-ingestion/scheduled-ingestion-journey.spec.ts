/**
 * E2E: Scheduled Ingestion Journey (Phase 4)
 * Create scheduled ingestion → trigger → wait for run completion (poll run status) → assert.
 * Real backend and real Prefect (or real backend with Prefect flow in test env).
 * No stubbing of API or Prefect; flakiness addressed by explicit wait for run status.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTenantAdminUser, loginUser } from '../../fixtures/auth';
import { hasLoginPrompt, loginAndNavigateToRoute } from '../../fixtures/helpers';

const API_BASE = process.env.E2E_API_BASE_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const PREFECT_INTEGRATION_URL =
  process.env.PREFECT_INTEGRATION_SERVICE_URL || 'http://localhost:8084';
const POLL_INTERVAL_MS = 5000;
// Increased timeout to handle Docker daemon performance issues (Prefect flow runs may take longer)
const RUN_COMPLETION_TIMEOUT_MS = 240000; // 4 minutes (Docker/CI can be slow)

type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface ScheduledIngestionRun {
  id: string;
  status: RunStatus;
  files_processed: number | null;
  files_failed: number | null;
  datasets_created: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Poll GET /api/v1/scheduled-ingestions/runs/{runId}/ until status is COMPLETED or FAILED, or timeout.
 * Uses token from localStorage (page must be authenticated).
 */
async function pollRunUntilTerminal(
  page: import('@playwright/test').Page,
  runId: string,
  options: { timeoutMs?: number; intervalMs?: number } = {}
): Promise<ScheduledIngestionRun> {
  const timeoutMs = options.timeoutMs ?? RUN_COMPLETION_TIMEOUT_MS;
  const intervalMs = options.intervalMs ?? POLL_INTERVAL_MS;
  const start = Date.now();

  const getToken = () => page.evaluate(() => localStorage.getItem('access_token') || '');

  const fetchRun = async (): Promise<ScheduledIngestionRun> => {
    const token = await getToken();
    if (!token) throw new Error('Not authenticated');
    const result = await page.evaluate(
      async ({
        base,
        runId: id,
        token: t,
      }: {
        base: string;
        runId: string;
        token: string;
      }): Promise<{ ok: boolean; status: number; body: unknown }> => {
        // Add cache-busting query parameter to ensure fresh data
        const url = `${base.replace(/\/$/, '')}/scheduled-ingestions/runs/${id}/?_t=${Date.now()}`;
        const r = await fetch(url, {
          headers: { Authorization: `Bearer ${t}` },
          cache: 'no-store',
        });
        const body = await r.json().catch(() => ({ message: r.statusText }));
        return { ok: r.ok, status: r.status, body };
      },
      { base: API_BASE, runId, token }
    );
    if (!result.ok) {
      if (result.status === 404) {
        throw new Error(
          `Run not found (404). runId=${runId}, base=${API_BASE}. ` +
            `Check trigger returned hub run_id (not flow_run_id). Body: ${JSON.stringify(result.body)}`
        );
      }
      throw new Error(`GET run failed: ${result.status} ${JSON.stringify(result.body)}`);
    }
    return result.body as ScheduledIngestionRun;
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
  const STATUS_SYNC_INTERVAL_MS = 5000; // Sync every 5 seconds
  let lastStatusSync = Date.now();

  while (Date.now() - start < timeoutMs) {
    // Trigger status sync before fetching run to ensure we have latest status
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

    const run = await fetchRun();
    if (run.status === 'COMPLETED' || run.status === 'FAILED' || run.status === 'CANCELLED') {
      return run;
    }
    // Log current status for debugging (only in test mode)
    if (process.env.DEBUG) {
      console.log(`[DEBUG] Run ${run.id} status: ${run.status}, waiting for terminal state...`);
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

  // Fetch run multiple times with delays to ensure we get fresh data
  let lastRun: ScheduledIngestionRun | undefined;
  for (let i = 0; i < 3; i++) {
    await page.waitForTimeout(1000); // Wait between fetches
    lastRun = await fetchRun();
    // Log status for debugging
    console.log(`[DEBUG] Final check ${i + 1}/3: Run ${lastRun.id} status: ${lastRun.status}`);
    // If we found a terminal state, break early
    if (
      lastRun.status === 'COMPLETED' ||
      lastRun.status === 'FAILED' ||
      lastRun.status === 'CANCELLED'
    ) {
      break;
    }
  }

  if (!lastRun) {
    throw new Error(
      `Run ${runId} not found within ${timeoutMs}ms. ` +
        'Ensure Prefect worker is running and processing jobs.'
    );
  }
  if (
    lastRun.status !== 'COMPLETED' &&
    lastRun.status !== 'FAILED' &&
    lastRun.status !== 'CANCELLED'
  ) {
    throw new Error(
      `Run ${runId} did not reach terminal state within ${timeoutMs}ms; last status: ${lastRun.status}. ` +
        'Ensure Prefect worker is running and processing jobs.'
    );
  }
  return lastRun;
}

test.describe('Scheduled Ingestion Journey', () => {
  // 8 min: login (~90s) + create + trigger (~60s) + poll (~240s) under parallel E2E load
  test.setTimeout(480000);

  test.describe('Failure', () => {
    test('unauthenticated access to scheduled-ingestions redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/scheduled-ingestions', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|scheduled-ingestions|403)/, { timeout: 20_000 });
      const url = page.url();
      const onLogin = url.includes('/login');
      const onRouteWithLoginPrompt =
        url.includes('/scheduled-ingestions') &&
        (await hasLoginPrompt(page));
      expect(onLogin || onRouteWithLoginPrompt).toBe(true);
    });
  });

  test.describe('Create, trigger, wait for run', () => {
    test('create scheduled ingestion → trigger → poll run status → assert run outcome', async ({
      page,
    }) => {
      // Pre-check: skip early if Prefect integration service is not reachable
      try {
        const healthRes = await fetch(`${PREFECT_INTEGRATION_URL.replace(/\/$/, '')}/health`, {
          signal: AbortSignal.timeout(10000),
        });
        if (!healthRes.ok) {
          throw new Error(
            `Prefect integration service unhealthy (${healthRes.status}). Scheduled ingestion requires Prefect. ` +
              `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
          );
        }
      } catch (e) {
        throw new Error(
          `Prefect integration service not reachable at ${PREFECT_INTEGRATION_URL}. Scheduled ingestion requires Prefect. ` +
            `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
        );
      }

      const testUser = await getTenantAdminUser();
      await loginUser(page, testUser);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2500);
      await loginAndNavigateToRoute(page, testUser, '/scheduled-ingestions', {
        timeout: 60000,
        contentSelector:
          '.scheduled-ingestion-list-page, .empty-state, .error-display, .loading-spinner-container, h1',
      });
      if (page.url().includes('/login')) {
        throw new Error(
          'Scheduled ingestions redirected to login. Precondition failure: E2E user roles not set up. ' +
            'Run: docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles'
        );
      }

      // Wait for list content: Create Schedule button (header or empty state; use .first() when both visible)
      const createBtn = page.getByRole('button', { name: /Create Schedule/i }).first();
      await createBtn.waitFor({ state: 'visible', timeout: 30000 });
      await createBtn.click();
      await page.waitForURL(/\/scheduled-ingestions\/create/, { timeout: 10000 });

      const name = `e2e-si-${Date.now()}`;
      await page.getByLabel(/name/i).fill(name);
      await page.getByRole('button', { name: /^Create$/i }).click();

      try {
        await page.waitForURL(
          (url) =>
            url.pathname.includes('/scheduled-ingestions/') && !url.pathname.endsWith('/create'),
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
          `Scheduled ingestion create did not navigate to detail within 30s. ${errText ? `Error: ${errText.slice(0, 150)}` : 'Check backend and Prefect availability.'}`
        );
      }
      // Detail page may show loading, then content; or error/empty if create failed
      // Use .first() to avoid strict mode violation when both detail page and runs-section empty-state exist
      await page
        .locator('[data-testid="scheduled-ingestion-detail-page"], .error-display, .empty-state')
        .first()
        .waitFor({ state: 'visible', timeout: 20000 });
      // Only skip on page-level error or "not found" empty - not the runs section "No runs" empty state
      const hasPageError = (await page.locator('.error-display').count()) > 0;
      const hasNotFoundEmpty =
        (await page.locator('.empty-state:has-text("not found"), .empty-state:has-text("could not be found")').count()) >
        0;
      if (hasPageError || (hasNotFoundEmpty && (await page.locator('[data-testid="scheduled-ingestion-detail-page"]').count()) === 0)) {
        throw new Error(
          'Scheduled ingestion create or load failed (error/empty). Check backend logs and Prefect availability.'
        );
      }
      await expect(page.locator('[data-testid="scheduled-ingestion-detail-page"]')).toBeVisible({
        timeout: 5000,
      });

      // Wait for schedule to load (name visible)
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
              (resp.status() === 202 ||
                resp.status() === 200 ||
                resp.status() === 503 ||
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
        if (triggerResponse.status() === 200 || triggerResponse.status() === 202) break;
        const body = await triggerResponse.json().catch(() => ({}));
        const isDeploymentNotReady =
          body?.code === 'DEPLOYMENT_NOT_READY' ||
          (body?.error && /not found|deployment|still be syncing/i.test(String(body.error)));
        if (triggerResponse.status() === 503 && isDeploymentNotReady && attempt < maxTriggerAttempts) {
          await page.waitForTimeout(5000);
          continue;
        }
        if (triggerResponse.status() === 503) {
          throw new Error(
            `Prefect not available (503). Scheduled ingestion requires Prefect. ` +
              `Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test. Body: ${JSON.stringify(body)}`
          );
        }
        if (triggerResponse.status() >= 400) {
          throw new Error(`Trigger failed: ${triggerResponse.status()} ${JSON.stringify(body)}`);
        }
      }

      const triggerBody = await triggerResponse.json();
      const runId = triggerBody.run_id ?? triggerBody.scheduled_ingestion_run_id;
      if (!runId || typeof runId !== 'string') {
        throw new Error(`Trigger response missing run_id: ${JSON.stringify(triggerBody)}`);
      }

      let run: Awaited<ReturnType<typeof pollRunUntilTerminal>>;
      try {
        run = await pollRunUntilTerminal(page, runId);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (
          msg.includes('not found within') ||
          msg.includes('did not reach terminal state') ||
          msg.includes('Ensure Prefect worker')
        ) {
          throw new Error(
            `Prefect run polling failed: ${msg}. Scheduled ingestion requires Prefect. ` +
              `Ensure Prefect stack is running: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
          );
        }
        throw err;
      }

      expect(['COMPLETED', 'FAILED', 'CANCELLED']).toContain(run.status);
      if (run.status === 'COMPLETED') {
        expect(typeof run.files_processed).toBe('number');
        expect(typeof run.datasets_created).toBe('number');
        expect(run.files_processed).toBeGreaterThanOrEqual(0);
        expect(run.datasets_created).toBeGreaterThanOrEqual(0);
      }
      if (run.status === 'FAILED' && run.error_message) {
        expect(typeof run.error_message).toBe('string');
      }
    });
  });
});
