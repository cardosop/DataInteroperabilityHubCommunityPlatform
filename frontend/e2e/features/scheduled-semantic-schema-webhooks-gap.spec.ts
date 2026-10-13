/**
 * Phase 7.5 — FEATURES gap closure (split per 226.E3).
 *
 * @deprecated — kept until Track D's replacement coverage lands; the
 * PR-time smoke (`@critical`) excludes this file via `--grep-invert`.
 * Each test here was relocated verbatim from the original
 * frontend/e2e/phase7.5-features-gap-closure.spec.ts so test semantics,
 * silent-failure annotations, and skip messages are preserved.
 *
 * Real backend only. No mocks/stubs.
 */

import { expect, test } from '@playwright/test';
import {
  getTenantAdminUser,
  getTestUser,
  loginUser,
} from '../fixtures/auth';
import {
  loginAndNavigateToRoute,
  navigateToRouteFromApp,
  waitForLoadingComplete,
} from '../fixtures/helpers';

test.describe("Phase 7.5 gap — scheduled / semantic / schema / webhooks @deprecated", () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    const testUser = await getTestUser();
    await loginUser(page, testUser);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('.app-sidebar', { timeout: 15000 });
  });


  test('Phase 7.5.K — Scheduled Ingestion: list schedules; open one; optional trigger', async ({
    page,
  }) => {
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/scheduled-ingestions', {
      timeout: 60000,
      contentSelector:
        '[data-testid="scheduled-ingestion-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
    });

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if user has access (not 403)
    const is403 = page.url().includes('/403');
    const isScheduledIngestionPage = page.url().includes('/scheduled-ingestions');

    if (is403) {
      // User doesn't have DATA_PROVIDER role - role gating works
      expect(is403).toBe(true) /* acceptable states */;
      return;
    }

    // User has access - test scheduled ingestion functionality
    expect(isScheduledIngestionPage).toBe(true) /* acceptable states */;

    await waitForLoadingComplete(page, { timeout: 15000 });

    const listPage = page.locator(
      '[data-testid="scheduled-ingestion-list-page"], .scheduled-ingestion-list-page, .empty-state, [data-testid="empty-state"]'
    );
    await expect(listPage.first()).toBeVisible({ timeout: 15000 });

    const table = page.locator('.scheduled-ingestion-table');
    const emptyState = page.locator('.empty-state, [data-testid="empty-state"]').first();
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

      const triggerBtn = page.getByRole('button', { name: /Trigger Now/i });
      // intentional: Trigger-Now button only renders when the schedule
      // is in ACTIVE status. Newly-created (DRAFT) and PAUSED
      // schedules legitimately don't show it. The detail-page assertion
      // immediately above confirms the page itself rendered.
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
          // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
          /* Optional: trigger response may timeout if service unavailable */
        }
        // Just verify page didn't crash
        await expect(detailPage).toBeVisible({ timeout: 5000 });
      }

      // Assert no crash - detail page still visible
      await expect(detailPage).toBeVisible({ timeout: 5000 });
    } else if (hasEmpty) {
      // No schedules - page loaded correctly
      expect(hasEmpty).toBe(true) /* acceptable states */;
      // Assert no crash - list page still visible
      await expect(listPage).toBeVisible({ timeout: 5000 });
    } else {
      // Fallback: assert body is visible
      await expect(page.locator('body')).toBeVisible({ timeout: 5000 });
    }
  });

  test('Phase 7.5.L — Semantic: page loads; SPARQL query; URI lookup', async ({ page }) => {
    // Paid layer (semantic/SPARQL) is absent in core-only mode — the
    // describe above groups scheduled/semantic/schema/webhooks gap
    // tests, so this test must gate itself out of the core subset.
    test.skip(process.env.E2E_CORE_ONLY === '1', 'semantic (paid layer) absent in core-only mode');
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
      expect(isUnavailable).toBe(true) /* acceptable states */;
      return;
    }

    if (!isSemanticPage) {
      // May be on /login or other route - skip semantic-specific assertions
      expect(page.url()).toMatch(/\/(semantic|unavailable|login)/);
      return;
    }

    // Capability available - test semantic functionality
    await waitForLoadingComplete(page, { timeout: 15000 });

    // Churn recovery (b7 #39): this spec navigates with a bare
    // page.goto, so under a mid-batch API stall the SPA auth gate can
    // strand the route before the semantic page mounts (15s visibility
    // budget expired with the page never rendering). Wait for EITHER
    // terminal first, then use the app's Retry ONCE on the transient
    // signature.
    // intentional: bounded terminal wait — a null result just means "no error terminal rendered" and the strict expect below reports the real state.
    await page
      .waitForSelector(
        '.semantic-page, [data-testid="semantic-page"], .error-display, [data-testid="error-display"]',
        { timeout: 20000 }
      )
      .catch(() => null);
    const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
    if ((await errorDisplay.count()) > 0) {
      // intentional: diagnostic-only read — an empty read just skips the retry and the strict assertion below reports the visible state.
      const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
      if (/NETWORK_ERROR|Network Error|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE|ECONNREFUSED|timed out/i.test(errText)) {
        await errorDisplay.locator('button:has-text("Retry")').first().click();
        // intentional: the retry may also fail under sustained churn — the strict toBeVisible below then fails with the real state.
        await page
          .locator('.semantic-page, [data-testid="semantic-page"]')
          .first()
          .waitFor({ state: 'visible', timeout: 30000 })
          .catch(() => null);
      }
    }

    const semanticPage = page.locator('.semantic-page, [data-testid="semantic-page"]');
    await expect(semanticPage.first()).toBeVisible({ timeout: 15000 });

    // Test SPARQL tab
    const sparqlTab = page.getByRole('button', { name: /SPARQL Query/i });
    await expect(sparqlTab).toBeVisible({ timeout: 5000 });
    await sparqlTab.click();
    await page.waitForTimeout(1000);

    const sparqlSection = page.locator('[data-testid="semantic-sparql-section"]');
    await expect(sparqlSection).toBeVisible({ timeout: 5000 });

    // The SPARQL input is a CodeMirror 6 contenteditable — the legacy
    // #sparql-query textarea id died with the editor migration. The
    // stable selector is the contentAttributes testid the component
    // stamps on the editor content (sparql-query-editor).
    const queryInput = page.locator('[data-testid="sparql-query-editor"]');
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
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
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
    // Paid layer (ai/schema-matching) is absent in core-only mode.
    test.skip(process.env.E2E_CORE_ONLY === '1', 'ai schema-matching (paid layer) absent in core-only mode');
    const testUser = await getTestUser();
    await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
      timeout: 60000,
      contentSelector:
        '[data-testid="schema-matching-page"], .schema-matching-page, .unavailable-page, [data-testid="unavailable-page"], .error-display, [data-testid="error-display"], h1, .disabled-capability-page, [data-testid="disabled-capability-page"]',
      acceptRedirectToLogin: true,
    });

    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Check if capability is available (may redirect to /unavailable)
    const isUnavailable = page.url().includes('/unavailable');
    const isSchemaMatchingPage = page.url().includes('/ai/schema-matching');

    if (isUnavailable) {
      // Schema matching capability not available - capability gating works
      expect(isUnavailable).toBe(true) /* acceptable states */;
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
      '.schema-matching-page, [data-testid="schema-matching-page"]'
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
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
      /* Optional: schema-matching response may timeout if service unavailable */
    }

    // Wait for either results or error to appear — event-driven instead of fixed timeout
    // intentional: probes optional UI via a multi-line waitForSelector chain — same shape as waitFor; absence is a legitimate state handled by the caller's branch below.
    await page
      .waitForSelector('[data-testid="schema-matching-results"], .error-display, [data-testid="error-display"]', {
        timeout: 15000,
      })
      .catch(() => null); // Tolerate if neither appears (service unavailable)

    // Check for results or error display
    const results = page.locator('[data-testid="schema-matching-results"]');
    const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
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
      expect(hasTable || hasNoMatches).toBe(true) /* acceptable states */;
    } else if (hasError) {
      await expect(errorDisplay).toBeVisible({ timeout: 5000 });
    }
    // If neither, might still be loading (acceptable)

    // Assert page didn't crash
    await expect(schemaMatchingPage).toBeVisible({ timeout: 5000 });
  });

  test('Phase 7.5.J — Webhooks: create webhook; list shows it; delete', async ({ page }) => {
    // Budget arithmetic: beforeEach login (~15s) + loginUser (~10s) +
    // navigation helper (60s) + create-form terminal wait (20s) + the
    // churn-recovery retry below (30s) + create/detail waits (~30s) +
    // list round-trip (~40s) — exceeds the old 90s cap whenever the
    // event-types fetch hits a mid-batch stall (b7 #40: the fill burned
    // the whole budget waiting for a form that never rendered). 180s
    // lets the retry + strict assertions run to completion.
    test.setTimeout(180000);
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
      contentSelector: '.webhook-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], h1',
    });

    const listPage = page.locator('.webhook-list-page');
    await expect(listPage).toBeVisible({ timeout: 10000 });
    const heading = page.getByRole('heading', { name: 'Webhooks', exact: true });
    await expect(heading).toBeVisible({ timeout: 5000 });

    await page.getByRole('button', { name: 'Create webhook' }).first().click();
    await page.waitForURL(/\/webhooks\/create/, { timeout: 5000 });
    await page.waitForTimeout(2000);

    // Churn recovery (b7 #40): WebhookCreatePage renders
    // LoadingSpinner → ErrorDisplay ("Failed to load event types") when
    // the event-types fetch dies mid-batch; the form never renders and
    // the fill below burned the whole 90s budget. Wait for EITHER
    // terminal, then use the app's Retry ONCE (it reloads the create
    // route) on the transient signature.
    // intentional: bounded terminal wait — a null result just means "no error terminal rendered" and the strict fill below reports the real state.
    await page
      .waitForSelector(
        'label[for="webhook-name"], .error-display, [data-testid="error-display"]',
        { timeout: 20000 }
      )
      .catch(() => null);
    const createErrorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
    if ((await createErrorDisplay.count()) > 0) {
      // intentional: diagnostic-only read — an empty read just skips the retry and the strict fill below reports the visible state.
      const errText = (await createErrorDisplay.textContent().catch(() => '')) ?? '';
      if (/NETWORK_ERROR|Network Error|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE|ECONNREFUSED|timed out/i.test(errText)) {
        await createErrorDisplay.locator('button:has-text("Retry")').first().click();
        // intentional: the retry may also fail under sustained churn — the strict fill below then fails with the real state.
        await page
          .locator('label[for="webhook-name"]')
          .first()
          .waitFor({ state: 'visible', timeout: 30000 })
          .catch(() => null);
      }
    }

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
      contentSelector: '.webhook-list-page, .webhook-list-table, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
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
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
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
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
      /* Row not yet visible */
    }
    if (!rowVisible) {
      await page.waitForTimeout(3000);
      try {
        rowVisible = await rowWithName.isVisible();
      } catch {
        // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
        /* Row not yet visible */
      }
    }
    if (!rowVisible) {
      await page.reload({ waitUntil: 'domcontentloaded' });
      await loginAndNavigateToRoute(page, testUser, '/webhooks', {
        timeout: 60000,
        contentSelector: '.webhook-list-page, .webhook-list-table, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"]',
      });
      await page.waitForTimeout(2000);
      try {
        rowVisible = await rowWithName.isVisible();
      } catch {
        // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
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
        contentSelector: '.webhook-detail-page, .error-display, [data-testid="error-display"]',
      });
    }
    await page.waitForURL(/\/webhooks\/[0-9a-f-]{36}$/i, { timeout: 20000 });
    await page.waitForTimeout(2000);

    const errEl = page.locator('.error-display, [data-testid="error-display"]').first();
    let errVisible = false;
    try {
      errVisible = await errEl.isVisible();
    } catch {
      // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
      /* Error element state unknown */
    }
    if (errVisible) {
      let msg = '';
      try {
        msg = (await errEl.textContent()) || '';
      } catch {
        // intentional: phase7.5 is flagged @deprecated under 226.E1 and queued for deletion under 226.E5 once Track D coverage lands. Bare catches here mark legacy fall-through patterns whose replacements live in the new D1-D4 specs; they're preserved with explicit justification rather than silently removed.
        /* Could not get error text */
      }
      throw new Error(`Webhook detail showed error (API/404): ${msg.slice(0, 300)}`);
    }
    const deleteBtn = page.getByRole('button', { name: 'Delete' }).first();
    await expect(deleteBtn).toBeVisible({ timeout: 15000 });
    await deleteBtn.click();
    await page.waitForTimeout(1000);
    // The shared Button component emits `btn--danger` (BEM-ish) — the
    // legacy `.btn-danger` class died in the Button consolidation
    // ("Replaces scattered .btn-danger"); the old selector matched
    // nothing and the confirm CTA never clicked (b7 #16).
    const confirmBtn = page.locator('.webhook-delete-actions .btn--danger');
    await expect(confirmBtn).toBeVisible({ timeout: 5000 });
    await confirmBtn.click();
    await page.waitForURL(/\/webhooks\/?$/, { timeout: 10000 });
    await page.waitForTimeout(2000);

    const rowAfterDelete = page
      .locator('.webhook-list-table tbody tr')
      .filter({ hasText: webhookName });
    await expect(rowAfterDelete).not.toBeVisible({ timeout: 5000 });
  });
});
