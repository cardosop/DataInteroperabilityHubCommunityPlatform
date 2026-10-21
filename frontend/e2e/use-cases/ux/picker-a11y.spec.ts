/**
 * Resource Picker Accessibility Tests (axe-core) — with auth
 * Per task 29.69.8.5. Runs axe on pages that actually render picker components.
 * Requires backend + auth (runs with main E2E config, not playwright.a11y.config).
 * No mocks; real pages with real pickers.
 */
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { getTenantAdminUser } from '../../fixtures/auth';
import {
  loginAndNavigateToRoute,
  waitForLoadingComplete,
} from '../../fixtures/helpers';

test.describe('Resource Picker Accessibility (axe, authenticated)', () => {
  test.setTimeout(90000);

  test('Scheduled Export create page (multi-pickers, ContractPicker) has no critical a11y violations', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/scheduled-exports/create', {
      timeout: 60000,
      contentSelector:
        '.scheduled-export-create-page, h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    // Only fail on critical/serious violations — minor/moderate are tracked separately
    const criticalViolations = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(criticalViolations).toEqual([]);
  });

  test('Retention Policy create page (AssetPicker, DatasetPicker, FilePicker) has no critical a11y violations', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/governance/retention/new', {
      timeout: 60000,
      contentSelector:
        '.governance-retention-policy-create-page, h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    // Only fail on critical/serious violations — minor/moderate are tracked separately
    const criticalViolations = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(criticalViolations).toEqual([]);
  });

  test('Dataset create page with AssetPicker (linkMode=existing) has no critical a11y violations', async ({
    page,
  }) => {
    const user = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, user, '/datasets/create?linkMode=existing', {
      timeout: 60000,
      contentSelector:
        '.dataset-create-page, [data-testid="dataset-create-page"], h1',
    });
    await waitForLoadingComplete(page, { timeout: 15000 });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    // Only fail on critical/serious violations — minor/moderate are tracked separately
    const criticalViolations = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(criticalViolations).toEqual([]);
  });
});
