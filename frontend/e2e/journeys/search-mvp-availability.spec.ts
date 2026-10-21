/**
 * Phase 273.1.10 — Search MVP availability E2E.
 *
 * Validates that /search is reachable in MVP mode:
 * - Sidebar shows Search entry
 * - Navigating to /search does NOT redirect to /coming-soon
 * - Typing a query hits the canonical /api/search/ endpoint
 *   (NOT the deprecated /api/v1/search/search/)
 */
import { expect, test } from '../fixtures/test-data-cleanup';
import { getTestUser } from '../fixtures/auth';

test.describe('273.1 Search MVP availability @critical', () => {
  test.setTimeout(120_000);

  test('search page is reachable and hits canonical endpoint', async ({
    page,
  }) => {
    const user = await getTestUser();
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);
    await page.click('[data-testid="login-submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15_000 });

    // Sidebar should show Search.
    await expect(
      page.locator('[data-testid="sidebar"] a[href="/search"]'),
    ).toBeVisible({ timeout: 10_000 });

    // Navigate to /search — should NOT redirect to /coming-soon.
    await page.goto('/search');
    await page.waitForURL('**/search', { timeout: 10_000 });
    expect(page.url()).toContain('/search');
    expect(page.url()).not.toContain('/coming-soon');

    // Type a query and verify the request hits the canonical endpoint.
    const [request] = await Promise.all([
      page.waitForRequest(
        (req) => req.url().includes('/api/search/'),
        { timeout: 10_000 },
      ),
      page.fill('[data-testid="search-input"]', 'test query'),
    ]);

    // Assert canonical endpoint, NOT deprecated.
    expect(request.url()).toContain('/api/search/');
    expect(request.url()).not.toContain('/api/v1/search/search/');

    // Search results should render.
    await expect(
      page.locator('[data-testid="search-results"]'),
    ).toBeVisible({ timeout: 10_000 });
  });
});
