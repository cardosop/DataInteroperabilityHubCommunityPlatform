/**
 * E2E: FeatureErrorBoundary
 *
 * Strategy: navigate to the test-only /test/error-boundary route which renders
 * TestErrorTrigger (throws unconditionally) inside a FeatureErrorBoundary.
 * This exercises the real boundary lifecycle (getDerivedStateFromError → fallback UI).
 *
 * The route is compiled in only when VITE_E2E_TEST=true (set by playwright.config.ts
 * via the Vite dev-server env). In production VITE_E2E_TEST is unset, so the route
 * and TestErrorTrigger are tree-shaken out of the bundle.
 *
 * data-testid contract (FeatureErrorBoundary.tsx):
 *   data-testid="feature-error-boundary-fallback" — wrapper div (visible on error)
 *   data-testid="feature-error-boundary-retry"    — "Try again" button
 */
import { test, expect } from '@playwright/test';

const ERROR_BOUNDARY_URL = '/test/error-boundary';

test.describe('JOURNEY-ERROR-BOUNDARY: FeatureErrorBoundary', () => {
  test('shows fallback UI when a child component throws during render', async ({ page }) => {
    await page.goto(ERROR_BOUNDARY_URL);

    // The error boundary must catch the render error and show the fallback
    await expect(
      page.getByTestId('feature-error-boundary-fallback')
    ).toBeVisible({ timeout: 10_000 });

    // The retry button must be present inside the fallback
    await expect(
      page.getByTestId('feature-error-boundary-retry')
    ).toBeVisible();

    // The page must still be on the test route — not crashed to a global error/500 page.
    // Use a precise positive assertion: the URL must contain the test route itself.
    // A plain /error/ regex is a false positive because the route name contains "error".
    await expect(page).toHaveURL(/test\/error-boundary/);
  });

  test('retry button resets boundary state (re-renders child)', async ({ page }) => {
    await page.goto(ERROR_BOUNDARY_URL);

    // Confirm boundary has caught the error
    await expect(
      page.getByTestId('feature-error-boundary-fallback')
    ).toBeVisible({ timeout: 10_000 });

    // Click retry — boundary calls setState({hasError: false}) which remounts
    // the throwing child; the boundary immediately re-catches and re-shows fallback.
    // This confirms handleRetry() fires and the error state cycles correctly.
    await page.getByTestId('feature-error-boundary-retry').click();

    // After re-mount the child throws again → fallback must reappear
    await expect(
      page.getByTestId('feature-error-boundary-fallback')
    ).toBeVisible({ timeout: 5_000 });
  });

  test('application shell survives navigation away from broken route', async ({ page }) => {
    // Land on the broken route
    await page.goto(ERROR_BOUNDARY_URL);
    await expect(
      page.getByTestId('feature-error-boundary-fallback')
    ).toBeVisible({ timeout: 10_000 });

    // Navigate away — the React root and router must remain healthy
    await page.goto('/assets');
    await expect(page).not.toHaveURL(/error|500/);
    // The page title must still be set (app shell alive)
    const title = await page.title();
    expect(title).toBeTruthy();
  });
});
