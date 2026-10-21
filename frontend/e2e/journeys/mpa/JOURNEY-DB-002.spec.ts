/**
 * E2E Test: JOURNEY-DB-002 — Test Workspace Connection and Rotate Credentials
 *
 * Journey: Test Workspace Connection and Rotate Credentials
 * Persona: Marketplace Platform Admin
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-002.md
 *
 * Real backend: a workspace + credential are provisioned through the REAL
 * API (encrypted at rest), then the page's Test action drives the real
 * probe. The credential is deliberately invalid, so the masked failure
 * path is exercised — the UI must surface the machine-readable
 * ``DATABRICKS_AUTH_FAILED`` code without echoing credential material.
 */

import { expect, test, type APIRequestContext } from '@playwright/test';
import { getTenantAdminUserOrTestUser, loginViaApi } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

async function seedWorkspaceWithBadCredential(
  request: APIRequestContext,
  accessToken: string
): Promise<string> {
  const unique = Date.now().toString().slice(-8);
  const headers = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  };
  const createResp = await request.post('/api/v1/databricks/workspaces/', {
    headers,
    data: {
      name: `e2e-db002-${unique}`,
      host: 'dbc-6710eb95-8fe1.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
    },
  });
  const workspace = (await createResp.json()) as { id?: string };
  if (!createResp.ok() || !workspace.id) {
    throw new Error(`workspace seed failed: ${createResp.status()}`);
  }
  const credResp = await request.post(
    `/api/v1/databricks/workspaces/${workspace.id}/credentials/`,
    {
      headers,
      data: { auth_mode: 'PAT', config: { token: 'dapi-e2e-invalid' } },
    }
  );
  if (!credResp.ok()) {
    throw new Error(`credential seed failed: ${credResp.status()}`);
  }
  return workspace.id;
}

test.describe('JOURNEY-DB-002: Test Workspace Connection and Rotate Credentials', () => {
  test.setTimeout(240000);

  test.describe('Failure (masked)', () => {
    test('test action surfaces the masked DATABRICKS_AUTH_FAILED code', async ({
      page,
      request,
    }) => {
      const user = await getTenantAdminUserOrTestUser();
      const auth = await loginViaApi(user.email, user.password);
      const workspaceId = await seedWorkspaceWithBadCredential(request, auth.access_token);

      await loginAndNavigateToRoute(page, user, '/databricks', {
        timeout: 60000,
        contentSelector:
          '.warehouse-list, [data-testid="databricks-flag-disabled"], .error-display',
      });

      // Journey step 2: run the connection test from the row action.
      const testButton = page.getByRole('button', { name: /^Test$/ }).first();
      await expect(testButton).toBeVisible({ timeout: 30000 });
      await testButton.click();

      // The masked failure reaches the UI WITH its code — never the token.
      await expect(page.locator('[role="alert"]')).toContainText(
        'DATABRICKS_AUTH_FAILED',
        { timeout: 60000 }
      );
      const bodyText = await page.textContent('body');
      expect(bodyText).not.toContain('dapi-e2e-invalid');
      expect(workspaceId).toBeTruthy();
    });
  });
});
