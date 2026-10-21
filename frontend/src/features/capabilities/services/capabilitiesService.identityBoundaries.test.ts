/**
 * W5.2 (oss-release-remediation R2-F2) — pins for the tenant-keyed
 * capabilities cache + the identity-boundary invalidation.
 *
 * The REAL service runs against a transport mock (the apiClient module —
 * the existing test file's convention: the HTTP layer is infrastructure,
 * the service under test is real). The REAL cacheIdentity bus drives the
 * logout/login invalidation pins — the service registers its invalidator
 * at import, exactly as production does.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const tenantState: { current: string | null } = { current: null };
const mockGet = vi.fn();

vi.mock('../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({ get: mockGet }),
    getEffectiveTenantId: () => tenantState.current,
  },
}));

import { invalidateIdentityCaches } from '../../../shared/services/cacheIdentity';
import { capabilitiesService } from './capabilitiesService';

/** Queue one manifest load: manifest response + runtime snapshot response.
 * ``databricks`` rides in BOTH (the manifest is path-derived — the real
 * backend never sends it there, so the snapshot response is the source
 * the service overlay reads; mirroring that split keeps the pins honest). */
function queueLoad(runtime: Record<string, unknown> = {}) {
  mockGet
    .mockResolvedValueOnce({
      data: { capabilities: { databricks: runtime.databricks !== false } },
    })
    .mockResolvedValueOnce({
      data: {
        capabilities: {
          asset_creation: runtime.asset_creation !== false,
          databricks: runtime.databricks !== false,
        },
      },
    });
}

async function loadFor(
  tenantId: string,
  runtime: Record<string, unknown> = {},
): Promise<void> {
  tenantState.current = tenantId;
  queueLoad(runtime);
  await capabilitiesService.loadCapabilities(true);
}

describe('capabilitiesService identity boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    tenantState.current = null;
    // A clean per-test state: the logout boundary wipes every entry.
    invalidateIdentityCaches('logout');
  });

  it('tenant switch isolates cached capabilities (no cross-tenant render source)', async () => {
    await loadFor('tenant-a', { databricks: true }); // databricks: true
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);

    await loadFor('tenant-b', { databricks: false }); // databricks: false
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);

    // Switching BACK serves tenant A's own entry — never B's.
    tenantState.current = 'tenant-a';
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);
  });

  it('the runtime snapshot is per-tenant (asset_creation gate)', async () => {
    await loadFor('tenant-a', { databricks: true, asset_creation: true });
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(true);

    await loadFor('tenant-b', { databricks: true, asset_creation: false });
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(false);

    tenantState.current = 'tenant-a';
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(true);
  });

  it('switching back within the TTL reuses the entry (no refetch)', async () => {
    await loadFor('tenant-a');
    await loadFor('tenant-b');
    const callsAfterBothLoads = mockGet.mock.calls.length;

    tenantState.current = 'tenant-a';
    const caps = await capabilitiesService.loadCapabilities(); // TTL hit
    expect(caps).toBeTruthy();
    expect(mockGet.mock.calls.length).toBe(callsAfterBothLoads);
  });

  it('forceRefresh refreshes ONLY the current tenant entry', async () => {
    await loadFor('tenant-a');
    await loadFor('tenant-b');
    const callsAfterBothLoads = mockGet.mock.calls.length;

    queueLoad(); // the forced tenant-B refresh's own responses
    await capabilitiesService.loadCapabilities(true); // force: tenant-b
    expect(mockGet.mock.calls.length).toBe(callsAfterBothLoads + 2); // manifest + snapshot for B only

    // Tenant A's entry survived the forced refresh — switch back, no fetch.
    tenantState.current = 'tenant-a';
    await capabilitiesService.loadCapabilities();
    expect(mockGet.mock.calls.length).toBe(callsAfterBothLoads + 2);
  });

  it('logout clears EVERY tenant entry', async () => {
    await loadFor('tenant-a', { databricks: true });
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);

    invalidateIdentityCaches('logout');
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);

    // Even switching back to a previously-loaded tenant serves nothing —
    // the identity ended; the next load must refetch.
    tenantState.current = 'tenant-a';
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);
    queueLoad({ databricks: true });
    await capabilitiesService.loadCapabilities();
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);
  });

  it('login clears the previous identity entries', async () => {
    await loadFor('tenant-a', { databricks: true });
    invalidateIdentityCaches('login');
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);
  });

  it('useFallbackCapabilities is per-tenant', async () => {
    await loadFor('tenant-a', { databricks: true });
    await loadFor('tenant-b', { databricks: true });
    capabilitiesService.useFallbackCapabilities();
    // Tenant B now serves the fallback map (auth.register always true).
    expect(capabilitiesService.isCapabilityAvailable('auth.register')).toBe(true);
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);

    // Tenant A's real entry is untouched by B's fallback.
    tenantState.current = 'tenant-a';
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);
  });
});
