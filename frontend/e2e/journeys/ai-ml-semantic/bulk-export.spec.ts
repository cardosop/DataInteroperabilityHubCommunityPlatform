/**
 * Phase 230.2.11 — E2E for the bulk RDF export tab
 * (REQ-SEM-EXPORT-001).
 *
 * Drives the Export tab on /semantic in a real browser:
 *
 *  1. Navigate to /semantic, click the Export tab.
 *  2. Pick a format from the dropdown.
 *  3. Click Download — assert the request URL contains
 *     ``/api/v1/semantic/export`` and a download is initiated.
 *  4. Inspect the Last-export size indicator.
 *
 * Negative paths:
 *
 *  - 413 (cap exceeded) and 429 (throttle) are not asserted in E2E
 *    because they require seeding an oversized dataset / hitting the
 *    rate limit; pinned by the backend test suite at
 *    [hub/apps/semantic/tests/test_views_export.py].
 */
import { test, expect } from '../../fixtures/guardedTest';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';


test.describe('Bulk RDF export — happy path', () => {
  test('download button POSTs /api/v1/semantic/export and triggers a download', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginUser(page, user);
    await loginAndNavigateToRoute(page, '/semantic', user);

    // Switch to the Export tab.
    await page.getByRole('button', { name: 'Export' }).click();
    const section = page.getByTestId('semantic-export-section');
    await expect(section).toBeVisible();

    // Pick Turtle (any format works — the assertion is on the
    // request shape, not the body).
    await page.getByTestId('semantic-export-format').selectOption('turtle');

    // Capture the request the Download button initiates AND the
    // browser download event in parallel — Playwright's
    // `waitForEvent('download')` arms before the click.
    const requestWaiter = page.waitForRequest(
      (req) =>
        req.url().includes('/api/v1/semantic/export') &&
        req.method() === 'POST',
    );
    const downloadWaiter = page.waitForEvent('download');
    await page.getByTestId('semantic-export-download').click();

    const req = await requestWaiter;
    // The body carries `{format: "turtle"}` — verified at the
    // request level so we don't depend on the file contents (which
    // depend on whatever's in the tenant's graph).
    const body = req.postDataJSON();
    expect(body).toMatchObject({ format: 'turtle' });

    const download = await downloadWaiter;
    // The suggested filename uses the .ttl extension per the format
    // mapping in SemanticPage.tsx.
    expect(download.suggestedFilename()).toMatch(/\.ttl$/);

    // The size indicator surfaces post-download (the `aria-live` is
    // polite so it doesn't steal focus — but the testid is stable).
    await expect(page.getByTestId('semantic-export-size')).toBeVisible();
  });
});
