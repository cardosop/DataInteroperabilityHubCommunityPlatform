import { describe, expect, it } from 'vitest';
import { userHasAnyRequiredRole } from './userRoles';

const complianceAllowlist = [
  'TENANT_ADMIN',
  'DATA_PROVIDER',
  'AUDITOR',
  'COMPLIANCE_OFFICER',
  'PLATFORM_ADMIN',
] as const;

describe('userHasAnyRequiredRole — Phase 231.6 parity', () => {
  it('allows empty requiredRole list', () => {
    expect(userHasAnyRequiredRole(null, undefined)).toBe(true);
    expect(userHasAnyRequiredRole({ roles: [] }, [])).toBe(true);
  });

  it('denies when no user', () => {
    expect(userHasAnyRequiredRole(null, ['TENANT_ADMIN'])).toBe(false);
  });

  it('allows when any JWT role matches', () => {
    expect(
      userHasAnyRequiredRole({ roles: ['DATA_CONSUMER'] }, [...complianceAllowlist]),
    ).toBe(false);
    expect(
      userHasAnyRequiredRole({ roles: ['AUDITOR'] }, [...complianceAllowlist]),
    ).toBe(true);
  });

  it('allows platform admin when allowlist includes PLATFORM_ADMIN even if roles[] omits it', () => {
    expect(
      userHasAnyRequiredRole(
        { roles: [], is_platform_admin: true },
        [...complianceAllowlist],
      ),
    ).toBe(true);
  });

  it('does not grant platform-admin bypass when PLATFORM_ADMIN is not in requiredRole', () => {
    expect(
      userHasAnyRequiredRole(
        { roles: [], is_platform_admin: true },
        ['TENANT_ADMIN', 'DATA_PROVIDER'],
      ),
    ).toBe(false);
  });
});
