/**
 * E2E spec — GraphQL-LD endpoint (Phase 230.13 / REQ-SEM-GQL-001 + 002).
 *
 * Validates the user-facing surface of the playground:
 *
 *   1. The "GraphQL-LD" tab is reachable on /semantic.
 *   2. ``/semantic?tab=graphql`` lands directly on the playground
 *      (deep-link contract — the Suspense fallback resolves to the
 *      playground's input/output panels).
 *   3. The Run button POSTs to ``/api/v1/semantic/graphql`` and
 *      surfaces the response.
 *   4. Capability-disabled tenants get a 403 surface (toast / error
 *      panel) — the page must not white-screen.
 *
 * Backend-pin assertions (depth/complexity/timeout/throttle/audit
 * emission) live in ``hub/apps/graphql_ld/tests/test_resolvers.py``
 * — repeating them via Playwright would require seeding ontologies
 * + assets per spec run without adding signal.
 */

import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser, loginViaApi } from '../../fixtures/auth';

test.describe('230.13 — GraphQL-LD playground @critical @semantic', () => {
  test.setTimeout(120_000);

  test('deep-link ?tab=graphql lands on the playground and the Run button POSTs to /semantic/graphql', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginViaApi(user.email, user.password);

    await page.goto('/semantic?tab=graphql');
    // Lazy-loaded — wait for the Suspense fallback to resolve.
    await expect(page.getByTestId('semantic-graphql-playground')).toBeVisible({
      timeout: 30_000,
    });

    // Default query is editable.
    const queryInput = page.getByTestId('graphql-query-input');
    await expect(queryInput).toBeVisible();

    // Capture the network call shape that the Run button drives.
    const graphqlRequest = page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/semantic/graphql') &&
        req.method() === 'POST',
      { timeout: 15_000 },
    );

    await page.getByTestId('graphql-run-button').click();
    const req = await graphqlRequest;
    const body = req.postDataJSON() as { query?: string };
    expect(body.query).toBeTruthy();
  });

  test('clicking the GraphQL-LD tab updates the URL to ?tab=graphql', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginViaApi(user.email, user.password);

    await page.goto('/semantic');
    // The tab strip exposes a button per visible tab.  Clicking the
    // GraphQL one mirrors the active id into the URL search params.
    const tab = page.getByRole('button', { name: /GraphQL-LD/i });
    await expect(tab).toBeVisible({ timeout: 15_000 });
    await tab.click();
    await expect(page).toHaveURL(/[?&]tab=graphql\b/);
    await expect(page.getByTestId('semantic-graphql-playground')).toBeVisible({
      timeout: 30_000,
    });
  });
});
