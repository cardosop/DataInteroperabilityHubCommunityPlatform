/**
 * Phase 278.V.5 [P0] — Persona-aware home dashboard E2E test.
 *
 * Validates that the RoleDashboard component renders persona-appropriate
 * widgets based on the authenticated user's roles (via usePersona()),
 * and that cross-persona isolation prevents forbidden widgets from
 * appearing for the wrong persona.
 *
 * @covers 278.V.5, 278.B.3, 278.R.6 — Persona-aware home dashboard E2E test
 * Spec ref: specs/ux-activation/activation-flows/spec.md (278.R.3)
 * Implementation ref: usePersona() hook + RoleDashboard + HomePage
 *
 * Persona → role mapping (source of truth: usePersona.ts):
 *   CPO  = PLATFORM_ADMIN + is_platform_admin → pending approvals
 *   DPO  = AUDITOR                          → audit events + compliance
 *   DE   = DATA_PROVIDER or TENANT_ADMIN    → draft assets
 *   DC   = DATA_CONSUMER                    → orders + entitlements
 *   DEV  = DEVELOPER                        → developer portal
 *
 * @critical
 */

import { expect } from '@playwright/test';
import { test } from '../../fixtures/consoleCapture';
import {
  getPlatformAdminUser,
  getAuditorUser,
  getTenantAdminUser,
  getConsumerTestUser,
  loginAsPersona,
  loginUser,
  clearAuthStorage,
} from '../../fixtures/auth';
import type { TestUser } from '../../setup/create-test-user';

// User with both DATA_PROVIDER and DATA_CONSUMER roles — exercises the
// multi-role union path in RoleDashboard (hasProviderRole + hasConsumerRole).
const MULTI_ROLE_USER: TestUser = {
  email: 'e2e_tenant_b@example.com',
  password: 'TestPass123!',
  name: 'E2E Tenant-B User',
};

test.describe('Persona-Aware Home Dashboard (278.V.5) @critical', () => {
  test.setTimeout(120000);

  test.describe('Success — per-persona widgets', () => {
    test('CPO (PLATFORM_ADMIN) sees pending approvals widget and CPO subtitle', async ({
      page,
    }) => {
      await loginAsPersona(page, getPlatformAdminUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // CPO-specific widget: pending approvals
      await expect(page.getByTestId('role-card-pending-approvals')).toBeVisible();

      // HomePage subtitle reflects detected persona
      await expect(page.locator('.subtitle')).toContainText('Chief Product Officer');
    });

    test('DPO (AUDITOR) sees audit events + compliance summary widgets', async ({
      page,
    }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // DPO-specific widgets
      await expect(page.getByTestId('role-card-recent-audit')).toBeVisible();
      await expect(page.getByTestId('role-card-compliance-summary')).toBeVisible();

      // Subtitle reflects DPO persona
      await expect(page.locator('.subtitle')).toContainText('Data Protection Officer');
    });

    test('DE (TENANT_ADMIN / DATA_PROVIDER) sees draft assets widget', async ({
      page,
    }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // DE-specific widget: my draft assets
      await expect(page.getByTestId('role-card-my-draft-assets')).toBeVisible();

      // Subtitle reflects DE persona
      await expect(page.locator('.subtitle')).toContainText('Data Engineer');
    });

    test('DC (DATA_CONSUMER) sees orders + entitlements widgets', async ({
      page,
    }) => {
      await loginAsPersona(page, getConsumerTestUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // DC-specific widgets
      await expect(page.getByTestId('role-card-my-orders')).toBeVisible();
      await expect(page.getByTestId('role-card-my-entitlements')).toBeVisible();

      // Subtitle reflects DC persona
      await expect(page.locator('.subtitle')).toContainText('Data Consumer');
    });

    test('base dashboard sections are always present regardless of persona', async ({
      page,
    }) => {
      // Use any persona — the base sections should always render
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });

      // Shared sections present for every authenticated user
      await expect(page.getByTestId('home-system-status')).toBeVisible();
      await expect(page.getByTestId('home-quick-actions')).toBeVisible();
      await expect(page.getByTestId('governance-overview')).toBeVisible();
      await expect(page.getByTestId('home-recent-assets')).toBeVisible();
      await expect(page.getByTestId('home-recent-datasets')).toBeVisible();
      await expect(page.getByTestId('home-recent-jobs')).toBeVisible();
    });
  });

  test.describe('Failure — cross-persona isolation', () => {
    test('DC (consumer) does NOT see CPO or DPO admin widgets', async ({
      page,
    }) => {
      await loginAsPersona(page, getConsumerTestUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // Consumer must never see admin/auditor widgets
      await expect(page.getByTestId('role-card-pending-approvals')).not.toBeVisible();
      await expect(page.getByTestId('role-card-recent-audit')).not.toBeVisible();
      await expect(page.getByTestId('role-card-compliance-summary')).not.toBeVisible();
    });

    test('DE (provider) does NOT see consumer order widgets', async ({ page }) => {
      await loginAsPersona(page, getTenantAdminUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // Provider must never see consumer-specific order/entitlement cards
      await expect(page.getByTestId('role-card-my-orders')).not.toBeVisible();
      await expect(page.getByTestId('role-card-my-entitlements')).not.toBeVisible();
    });

    test('DPO (auditor) does NOT see provider or consumer widgets', async ({
      page,
    }) => {
      await loginAsPersona(page, getAuditorUser);
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // Auditor must never see provider/consumer widgets
      await expect(page.getByTestId('role-card-my-draft-assets')).not.toBeVisible();
      await expect(page.getByTestId('role-card-my-orders')).not.toBeVisible();
      await expect(page.getByTestId('role-card-my-entitlements')).not.toBeVisible();
    });

    test('unauthenticated visitor is redirected away from dashboard', async ({
      page,
    }) => {
      await clearAuthStorage(page);
      await page.goto('/', { waitUntil: 'domcontentloaded' });

      // Unauthenticated: must be redirected to login or see landing
      const url = page.url();
      const redirected = url.includes('/login') || url.includes('/landing');
      // If somehow still at /, home-page must not render persona-specific cards
      if (!redirected) {
        await expect(page.getByTestId('role-dashboard')).not.toBeVisible();
      }
      expect(redirected).toBe(true);
    });
  });

  test.describe('Edge — multi-role union', () => {
    test('user with DATA_PROVIDER + DATA_CONSUMER sees both DE and DC cards', async ({
      page,
    }) => {
      // e2e_tenant_b@example.com has roles [DATA_PROVIDER, DATA_CONSUMER].
      // usePersona() resolves to DE (DATA_PROVIDER checked first), but
      // RoleDashboard's hasConsumerRole union (roles.has('DATA_CONSUMER'))
      // ensures consumer cards also render. This validates multi-role union.
      await clearAuthStorage(page);
      await loginUser(page, MULTI_ROLE_USER, { forceFreshLogin: true });
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('home-page')).toBeVisible({ timeout: 15000 });
      await expect(page.getByTestId('role-dashboard')).toBeVisible({ timeout: 10000 });

      // DE cards: draft assets (from DATA_PROVIDER role)
      await expect(page.getByTestId('role-card-my-draft-assets')).toBeVisible();

      // DC cards: orders + entitlements (from DATA_CONSUMER role via union)
      await expect(page.getByTestId('role-card-my-orders')).toBeVisible();
      await expect(page.getByTestId('role-card-my-entitlements')).toBeVisible();
    });
  });
});
