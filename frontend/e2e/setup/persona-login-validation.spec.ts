/**
 * Validates that persona users (TA, AUD, PA, CPO, DEV, DMO) can log in via API.
 * Acceptance for 6.10.1.3: Tests can log in as TA, AUD, PA, CPO.
 * Phase 6.11.7: Extended to DEV, DMO.
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
} from '../fixtures/auth';

test.describe('Persona login validation (6.10.1.3, 6.11.7)', () => {
  test('getTenantAdminUser can login via API', async () => {
    const user = await getTenantAdminUser();
    expect(user.email).toBe('e2e_admin@example.com');
    expect(user.password).toBe('TestPass123');
  });

  test('getAuditorUser can login via API', async () => {
    const user = await getAuditorUser();
    expect(user.email).toBe('e2e_auditor@example.com');
    expect(user.password).toBe('TestPass123');
  });

  test('getPlatformAdminUser can login via API', async () => {
    const user = await getPlatformAdminUser();
    expect(user.email).toBe('e2e_platform@example.com');
    expect(user.password).toBe('TestPass123');
  });

  test('getComplianceOfficerUser can login via API', async () => {
    const user = await getComplianceOfficerUser();
    expect(user.email).toBe('e2e_cpo@example.com');
    expect(user.password).toBe('TestPass123');
  });

  test('getExternalDeveloperUser can login via API', async () => {
    const user = await getExternalDeveloperUser();
    expect(user.email).toBe('e2e_developer@example.com');
    expect(user.password).toBe('TestPass123');
  });

  test('getDataMeshDomainOwnerUser can login via API', async () => {
    const user = await getDataMeshDomainOwnerUser();
    expect(user.email).toBe('e2e_dmo@example.com');
    expect(user.password).toBe('TestPass123');
  });
});
