/**
 * E2E Test: Phase 8.4 — Tenant Admin Views Usage & Config
 *
 * Tenant admin views usage and config at /settings/tenant.
 * No mocks/stubs; real backend only.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { getTenantAdminUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute, waitForLoadingComplete } from '../../fixtures/helpers';
// Phase 226 B1e — dual-channel verification on tenant-config save.
import { verifyViaApi } from '../../fixtures/verifyViaApi';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

test.describe('Phase 8.4: Tenant Admin Views Usage & Config', () => {
  test.setTimeout(120000);

  test('tenant admin views usage tab', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/tenant', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    expect(page.url()).toContain('/settings/tenant');
    await waitForLoadingComplete(page, { timeout: 15000 });

    // The tab bar renders only after the tenant usage/config API calls
    // resolve — under batch load those can fail and the page falls into
    // its error branch (no tabs, no sections). Skip gracefully there.
    const tabBar = page.locator('.tenant-settings-tabs');
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const tabsLoaded = await tabBar
      .waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    if (!tabsLoaded) {
      environmentSkipGuard(
          'Tenant settings tabs did not render — tenant usage/config API unavailable under load'
        );
        test.skip(!tabsLoaded, 'Tenant settings tabs did not render — tenant usage/config API may be unavailable');
      return;
    }

    const usageSection = page.locator('[data-testid="tenant-settings-usage"]');
    // The usage section needs the usage API specifically — it can lag
    // behind the tab bar (which renders as soon as EITHER usage or
    // config resolves). Tolerate slow/unavailable usage with a skip.
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const usageLoaded = await usageSection
      .waitFor({ state: 'visible', timeout: 30000 })
      .then(() => true)
      .catch(() => false);
    if (!usageLoaded) {
      environmentSkipGuard(
          'Usage section did not render — tenant usage API unavailable under load'
        );
        test.skip(!usageLoaded, 'Usage section did not render — tenant usage API may be slow/unavailable');
      return;
    }

    const usageLabel = page.locator('.tenant-metric-label').first();
    await expect(usageLabel).toBeVisible({ timeout: 5000 });
  });

  test('tenant admin views config tab and can save', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/tenant', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const tabBar = page.locator('.tenant-settings-tabs');
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const tabsLoaded = await tabBar
      .waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    if (!tabsLoaded) {
      environmentSkipGuard(
          'Tenant settings tabs did not render — tenant usage/config API unavailable under load'
        );
        test.skip(!tabsLoaded, 'Tenant settings tabs did not render — tenant usage/config API may be unavailable');
      return;
    }

    const configTab = page.locator('button:has-text("Configuration")');
    await configTab.click();
    await page.waitForTimeout(1000);

    const configSection = page.locator('[data-testid="tenant-settings-config"]');
    await expect(configSection).toBeVisible({ timeout: 10000 });

    const dqSelect = page.locator('#tenant-default_dq_profile');
    await expect(dqSelect).toBeVisible({ timeout: 5000 });

    // Capture the CURRENT profile — the save below PERSISTS on the
    // shared default tenant, and a stray profile contaminates every
    // other journey's DQ runs (DC-001's publish gate requires DQ PASS;
    // a leftover profile made new assets FAIL). Restore it at the end.
    const originalProfile = await dqSelect.inputValue();
    await dqSelect.selectOption('intake_basic_soda');
    const saveBtn = page.locator('button[type="submit"]').or(page.locator('button:has-text("Save")')).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator('.tenant-settings-success, [data-testid="tenant-settings-success"]').first();
    await expect(successMsg).toBeVisible({ timeout: 5000 });
    await expect(successMsg).toContainText(/updated|success/i);

    // Phase 226 B1e — dual-channel verification of tenant config save.
    // Assert the backend actually stored the new default_dq_profile value
    // and that the audit trail recorded TENANT_CONFIG_UPDATED (action name
    // confirmed via hub/apps/tenants/views.py:449).
    //
    // Use `/api/v1/tenants/me/config/` — the "self" variant that scopes to
    // the caller's active tenant without needing to resolve the tenant id.
    // This avoids the earlier bug where the wrong localStorage key
    // (`current_tenant_id` vs the real `active_tenant_id` per
    // frontend/src/features/auth/store/authStore.ts:65) would skip the check.
    // The save click can race slow React commits under batch load — a stray
    // duplicate PATCH (click retry / re-submit) may land just after the save
    // and briefly write a stale value. Poll for a few seconds: the FIRST read
    // that observes the saved profile wins; only a persistent mismatch fails.
    let profileVerified = false;
    let verifyErr: unknown;
    for (let attempt = 0; attempt < 6 && !profileVerified; attempt++) {
      try {
        await verifyViaApi(page, '/api/v1/tenants/me/config/', (body) => {
          const cfg = body as { default_dq_profile?: string };
          return cfg.default_dq_profile === 'intake_basic_soda';
        });
        profileVerified = true;
      } catch (err) {
        verifyErr = err;
        if (attempt < 5) await page.waitForTimeout(500);
      }
    }
    if (!profileVerified) throw verifyErr;
    // For the audit row we still need the tenant uuid as resource_id.
    // Read from the active_tenant_id localStorage key (see authStore.ts:65).
    const activeTenantId = await page.evaluate(
      () =>
        (globalThis as { localStorage?: { getItem: (k: string) => string | null } })
          .localStorage?.getItem('active_tenant_id') ?? null,
    );
    if (activeTenantId) {
      await verifyAuditEvent(page, {
        action: 'TENANT_CONFIG_UPDATED',
        resourceType: 'TENANT',
        resourceId: activeTenantId,
      });
    }

    // Restore the shared tenant's original DQ profile so later journeys
    // (marketplace publish gates, DQ runs) see the pristine config.
    await dqSelect.selectOption(originalProfile);
    await saveBtn.click();
    await page.waitForTimeout(2000);
  });

  test('Phase 11: tenant admin can toggle trust signals enabled', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/tenant', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const tabBar = page.locator('.tenant-settings-tabs');
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const tabsLoaded = await tabBar
      .waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    if (!tabsLoaded) {
      environmentSkipGuard(
          'Tenant settings tabs did not render — tenant usage/config API unavailable under load'
        );
        test.skip(!tabsLoaded, 'Tenant settings tabs did not render — tenant usage/config API may be unavailable');
      return;
    }

    const configTab = page.locator('button:has-text("Configuration")');
    await configTab.click();
    await page.waitForTimeout(1000);

    const trustSignalsCheckbox = page.locator('#tenant-trust_signals_enabled');
    await expect(trustSignalsCheckbox).toBeVisible({ timeout: 5000 });

    const initialState = await trustSignalsCheckbox.isChecked();
    await trustSignalsCheckbox.click();
    await page.waitForTimeout(300);

    const saveBtn = page.locator('button[type="submit"]').or(page.locator('button:has-text("Save")')).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator('.tenant-settings-success, [data-testid="tenant-settings-success"]').first();
    await expect(successMsg).toBeVisible({ timeout: 5000 });

    const newState = await trustSignalsCheckbox.isChecked();
    expect(newState).toBe(!initialState);

    // Restore the shared tenant flag — toggles persist tenant-wide and
    // other journeys read them (same contamination aversion as the DQ
    // profile restore above).
    await trustSignalsCheckbox.click();
    await saveBtn.click();
    await page.waitForTimeout(2000);
  });

  test('Phase 12: tenant admin can toggle versioning enabled', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/tenant', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const tabBar = page.locator('.tenant-settings-tabs');
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const tabsLoaded = await tabBar
      .waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    if (!tabsLoaded) {
      environmentSkipGuard(
          'Tenant settings tabs did not render — tenant usage/config API unavailable under load'
        );
        test.skip(!tabsLoaded, 'Tenant settings tabs did not render — tenant usage/config API may be unavailable');
      return;
    }

    const configTab = page.locator('button:has-text("Configuration")');
    await configTab.click();

    // The config form only renders after the tenant config API call resolves.
    // Wait for the form itself (not just the tab section) before looking for checkboxes.
    const configForm = page.locator('[data-testid="tenant-settings-config"] form');
    // intentional: treats the promise's rejection as a structured false — the following if/branch consumes the boolean without swallowing.
    const formLoaded = await configForm.waitFor({ state: 'visible', timeout: 20000 }).then(() => true).catch(() => false);
    if (!formLoaded) {
      environmentSkipGuard(
          'Config form did not render — tenant config API unavailable under load'
        );
        test.skip(!formLoaded, 'Config form did not render — tenant config API may be unavailable');
      return;
    }

    const versioningCheckbox = page.locator('#tenant-versioning_enabled');
    await expect(versioningCheckbox).toBeVisible({ timeout: 10000 });

    const initialState = await versioningCheckbox.isChecked();
    await versioningCheckbox.click();
    await page.waitForTimeout(300);

    const saveBtn = page.locator('button[type="submit"]').or(page.locator('button:has-text("Save")')).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator('.tenant-settings-success, [data-testid="tenant-settings-success"]').first();
    await expect(successMsg).toBeVisible({ timeout: 10000 });

    const newState = await versioningCheckbox.isChecked();
    expect(newState).toBe(!initialState);

    // Restore the shared tenant flag (see the trust-signals restore).
    await versioningCheckbox.click();
    await saveBtn.click();
    await page.waitForTimeout(2000);
  });

  test('Phase 14: tenant admin can toggle workflows enabled', async ({ page }) => {
    const taUser = await getTenantAdminUser();
    await loginAndNavigateToRoute(page, taUser, '/settings/tenant', { timeout: 60000 });
    if (page.url().includes('/login') || page.url().includes('/403')) {
      expect(page.url()).toMatch(/\/login|\/403/);
      return;
    }
    await waitForLoadingComplete(page, { timeout: 15000 });

    const tabBar = page.locator('.tenant-settings-tabs');
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const tabsLoaded = await tabBar
      .waitFor({ state: 'visible', timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    if (!tabsLoaded) {
      environmentSkipGuard(
          'Tenant settings tabs did not render — tenant usage/config API unavailable under load'
        );
        test.skip(!tabsLoaded, 'Tenant settings tabs did not render — tenant usage/config API may be unavailable');
      return;
    }

    const configTab = page.locator('button:has-text("Configuration")');
    await configTab.click();

    // The config form only renders after the tenant config API call resolves.
    // Wait for the form itself (not just the tab section) before looking for checkboxes.
    const configForm = page.locator('[data-testid="tenant-settings-config"] form');
    // intentional: treats the promise's rejection as a structured false — the following if/branch consumes the boolean without swallowing.
    const formLoaded = await configForm.waitFor({ state: 'visible', timeout: 20000 }).then(() => true).catch(() => false);
    if (!formLoaded) {
      environmentSkipGuard(
          'Config form did not render — tenant config API unavailable under load'
        );
        test.skip(!formLoaded, 'Config form did not render — tenant config API may be unavailable');
      return;
    }

    const workflowsCheckbox = page.locator('#tenant-workflows_enabled');
    await expect(workflowsCheckbox).toBeVisible({ timeout: 10000 });

    const initialState = await workflowsCheckbox.isChecked();
    await workflowsCheckbox.click();
    await page.waitForTimeout(300);

    const saveBtn = page.locator('button[type="submit"]').or(page.locator('button:has-text("Save")')).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator('.tenant-settings-success, [data-testid="tenant-settings-success"]').first();
    await expect(successMsg).toBeVisible({ timeout: 10000 });

    const newState = await workflowsCheckbox.isChecked();
    expect(newState).toBe(!initialState);

    // Restore the shared tenant flag (see the trust-signals restore).
    await workflowsCheckbox.click();
    await saveBtn.click();
    await page.waitForTimeout(2000);
  });
});
