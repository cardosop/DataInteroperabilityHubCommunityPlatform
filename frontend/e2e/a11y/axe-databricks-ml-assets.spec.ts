/**
 * 12.6 — Databricks ML-assets page accessibility audit (the Shared DoD
 * frontend gate's a11y clause on the NEW page).
 *
 * Runs WCAG 2.1 AA axe checks against the flag-gated ML-assets
 * management page (`databricks/workspaces/:workspaceId/ml-assets` —
 * the 12.6 surface). The page's a11y contract:
 *
 * - the flag-off banner + the error surfaces render `role="alert"`
 *   (the screen-reader timeline — a state change is announced),
 * - every action is a native button (keyboard-operable: Enter/Space),
 * - the tables carry real `<th>` headers.
 *
 * The legs render the REAL page against the real backend with a
 * seeded workspace (the docker-exec provisioning pattern); the axe
 * audit covers the loaded state. The W16 policy governs the
 * environment guards (skipIfRemoteApi — never a bare skip).
 */
import { AxeBuilder } from '@axe-core/playwright';
import { execSync } from 'node:child_process';
import { expect, test } from '@playwright/test';

import { skipIfRemoteApi } from '../fixtures/helpers';
import { loginUser } from '../fixtures/auth';

interface Provisioned {
  workspace: string;
  email: string;
}

function provisionWorkspace(): Provisioned {
  skipIfRemoteApi(test, 'ML-assets a11y provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from hub.apps.tenants.models import Tenant
from hub.apps.databricks_admin.models import DatabricksWorkspace, DatabricksCloud
from hub.apps.users.models import User, Role, UserRole, UserStatus

tenant = Tenant.objects.create(name='ml-a11y-${suffix}', slug='ml-a11y-${suffix}')
tenant.databricks_control_plane_enabled = True
tenant.databricks_ml_assets_enabled = True
tenant.save(update_fields=['databricks_control_plane_enabled', 'databricks_ml_assets_enabled'])
user = User.objects.create_user(
    email='ml-a11y-${suffix}@test.com', password='testpass123',
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN')
UserRole.objects.get_or_create(user=user, role=role)
workspace = DatabricksWorkspace.objects.create(
    tenant=tenant, name='ws-ml-a11y-${suffix}',
    host='dbc-6710eb95-8fe1.cloud.databricks.com',
    cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
)
print(json.dumps({'workspace': str(workspace.id), 'email': user.email}))
`;
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"workspace"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  return JSON.parse(lines[0].trim()) as Provisioned;
}

test.describe('A11y: the databricks ML-assets page', () => {
  test.setTimeout(180000);

  test('the page audits clean under WCAG 2.1 AA', async ({ page }) => {
    const provisioned = provisionWorkspace();
    const user = { email: provisioned.email, password: 'testpass123' };
    await loginUser(page, user);
    await page.goto(`/databricks/workspaces/${provisioned.workspace}/ml-assets`);
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations,
      `axe violations: ${JSON.stringify(results.violations, null, 2)}`
    ).toEqual([]);
  });

  test('the surfaces announce state via role=alert and actions are keyboard-operable', async ({
    page,
  }) => {
    const provisioned = provisionWorkspace();
    const user = { email: provisioned.email, password: 'testpass123' };
    await loginUser(page, user);
    await page.goto(`/databricks/workspaces/${provisioned.workspace}/ml-assets`);
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    // The register form's input + button are native controls — Tab
    // reaches the button and Enter submits (keyboard nav).
    const registerInput = page.getByTestId('ml-register-input');
    await registerInput.waitFor({ timeout: 10_000 });
    await registerInput.press('Tab');
    await expect(page.getByTestId('ml-register-button')).toBeFocused();
    await page.getByTestId('ml-register-button').press('Enter');
    // The submit path renders the action-error surface (role=alert —
    // the screen-reader timeline) for the empty full_name (the
    // backend answers the classified 400 — a real, deterministic
    // surface, never a placeholder assertion).
    await expect(page.getByTestId('ml-assets-action-error')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('alert')).toBeVisible();
  });
});
