/**
 * Validates that persona users (TA, AUD, PA, CPO, DEV, DMO) can authenticate.
 *
 * Each test:
 *   1. Resolves the persona user fixture (ensures it exists via ensure_e2e_user_roles)
 *   2. Performs a real API login (POST /auth/login/) and asserts a token is returned
 *
 * This catches broken persona setup earlier than waiting for a full journey test to fail.
 * Acceptance: 6.10.1.3 (TA, AUD, PA, CPO), Phase 6.11.7 (DEV, DMO).
 * Requires: ensure_e2e_user_roles run before E2E (e2e-detect-api.sh does this when API on 8001).
 */

import { expect, test } from '@playwright/test';
import {
  getAuditorUser,
  getComplianceOfficerUser,
  getDataMeshDomainOwnerUser,
  getExternalDeveloperUser,
  getPlatformAdminUser,
  getTenantAdminUser,
  loginViaApi,
} from '../fixtures/auth';

test.describe('Persona login validation (6.10.1.3, 6.11.7)', () => {
  test.setTimeout(60000); // loginViaApi retries up to 5× with backoff

  test('getTenantAdminUser resolves and can authenticate via API', async () => {
    const user = await getTenantAdminUser();
    expect(user.email).toBe('e2e_admin@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });

  test('getAuditorUser resolves and can authenticate via API', async () => {
    const user = await getAuditorUser();
    expect(user.email).toBe('e2e_auditor@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });

  test('getPlatformAdminUser resolves and can authenticate via API', async () => {
    const user = await getPlatformAdminUser();
    expect(user.email).toBe('e2e_platform@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });

  test('getComplianceOfficerUser resolves and can authenticate via API', async () => {
    const user = await getComplianceOfficerUser();
    expect(user.email).toBe('e2e_cpo@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });

  test('getExternalDeveloperUser resolves and can authenticate via API', async () => {
    const user = await getExternalDeveloperUser();
    expect(user.email).toBe('e2e_developer@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });

  test('getDataMeshDomainOwnerUser resolves and can authenticate via API', async () => {
    const user = await getDataMeshDomainOwnerUser();
    expect(user.email).toBe('e2e_dmo@example.com');
    const auth = await loginViaApi(user.email, user.password);
    expect(typeof auth.access_token).toBe('string');
    expect(auth.access_token.length).toBeGreaterThan(0);
  });
});
