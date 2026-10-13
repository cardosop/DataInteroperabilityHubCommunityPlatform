/**
 * Capabilities service unit tests — OpenAPI fetch retry and fallback behavior.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockGet = vi.fn();

vi.mock('../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({ get: mockGet }),
  },
}));

import { capabilitiesService } from './capabilitiesService';

describe('capabilitiesService.loadCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retries once when the first OpenAPI request fails', async () => {
    // Phase 250.6.D.2 — ``loadCapabilities`` now also fetches
    // ``/api/v1/capabilities/`` for the per-tenant runtime snapshot.
    // The mock queue must therefore carry THREE responses: the
    // first OpenAPI attempt (fails), the OpenAPI retry (succeeds),
    // and the runtime-capabilities fetch (succeeds with a stub
    // payload).
    mockGet
      .mockRejectedValueOnce(new Error('manifest unavailable')) // manifest-first probe
      .mockRejectedValueOnce(new Error('transient network'))
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: true,
            asset_creation_blocked_reason: null,
          },
        },
      });

    const caps = await capabilitiesService.loadCapabilities(true);

    expect(mockGet).toHaveBeenCalledTimes(4);
    expect(caps['auth.register']?.available).toBe(true);
    // Runtime-snapshot fetch landed too — assert the reason getter
    // surfaces the stubbed value.
    expect(capabilitiesService.getAssetCreationBlockedReason()).toBeNull();
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(true);
  });

  it('exposes the onboarding-incomplete reason from the runtime snapshot', async () => {
    // Phase 250.6.D.2 — pin the reason discriminator pass-through.
    mockGet
      .mockRejectedValueOnce(new Error('manifest unavailable')) // manifest-first probe
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: false,
            asset_creation_blocked_reason: 'ONBOARDING_INCOMPLETE',
          },
        },
      });

    await capabilitiesService.loadCapabilities(true);

    expect(capabilitiesService.getAssetCreationBlockedReason()).toBe(
      'ONBOARDING_INCOMPLETE',
    );
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(false);
  });

  it('coerces unknown reason values to null (defensive)', async () => {
    // Phase 250.6.D.2 — backend returning a future enum value the
    // SPA doesn't yet know about MUST collapse to ``null`` rather
    // than leaking the raw string into typed UI code paths.
    mockGet
      .mockRejectedValueOnce(new Error('manifest unavailable')) // manifest-first probe
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: false,
            asset_creation_blocked_reason: 'UNKNOWN_FUTURE_REASON',
          },
        },
      });

    await capabilitiesService.loadCapabilities(true);
    expect(capabilitiesService.getAssetCreationBlockedReason()).toBeNull();
  });

  it('registers the databricks capability from the runtime snapshot', async () => {
    // openspec add-databricks-control-plane P0 — the /databricks route
    // gates on this key; before the wiring it resolved ``?? false`` for
    // every tenant (JOURNEY-DB-001 timed out waiting for the page).
    mockGet
      .mockRejectedValueOnce(new Error('manifest unavailable')) // manifest-first probe
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: true,
            asset_creation_blocked_reason: null,
            databricks: true,
          },
        },
      });

    await capabilitiesService.loadCapabilities(true);
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);
    expect(capabilitiesService.getCapability('databricks')?.available).toBe(true);
  });

  it('keeps databricks unavailable when the snapshot omits the key (strict opt-in)', async () => {
    mockGet
      .mockRejectedValueOnce(new Error('manifest unavailable')) // manifest-first probe
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: true,
            asset_creation_blocked_reason: null,
          },
        },
      });

    await capabilitiesService.loadCapabilities(true);
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);
  });
});

describe('capabilitiesService auth fallback map', () => {
  // Both full-failure paths converge on the same map:
  //   * loadCapabilities()'s catch (OpenAPI fetch failed every attempt)
  //   * useCapabilities' 30s load-timeout → useFallbackCapabilities()
  // Pin the shape directly so a future edit can't silently drop the
  // asset_creation fail-open and re-bounce /assets/create to /unavailable
  // on a transient capabilities hiccup (Phase 260.3.B / 250.6.D contract).
  it('keeps auth routes available', () => {
    capabilitiesService.useFallbackCapabilities();
    expect(capabilitiesService.isCapabilityAvailable('auth.register')).toBe(true);
    expect(capabilitiesService.isCapabilityAvailable('auth.password-reset')).toBe(
      true,
    );
  });

  it('keeps the asset-creation route reachable (fail-open kill switch)', () => {
    capabilitiesService.useFallbackCapabilities();
    const cap = capabilitiesService.getCapability('asset_creation');
    expect(cap?.available).toBe(true);
    expect(capabilitiesService.isCapabilityAvailable('asset_creation')).toBe(true);
  });

  it('keeps datasets/files reachable (Phase 260.3.B)', () => {
    capabilitiesService.useFallbackCapabilities();
    expect(capabilitiesService.isCapabilityAvailable('datasets')).toBe(true);
    expect(capabilitiesService.isCapabilityAvailable('files')).toBe(true);
  });

  it('keeps the marketplace reachable (313.H.4 fail-open)', () => {
    // A transient OpenAPI hiccup must not bounce the whole /marketplace
    // subtree to /unavailable — JOURNEY-MPA-002's PA landed there during
    // stack churn before this entry existed.
    capabilitiesService.useFallbackCapabilities();
    expect(capabilitiesService.isCapabilityAvailable('marketplace')).toBe(true);
  });

  it('keeps the lineage time-travel controls reachable (228 F5 fail-open)', () => {
    // The controls gate on 'lineage.snapshots' and the gate is UX-only
    // (the backend silently ignores the anchor params when the flag is
    // off). Every load-failure path installs this map — without these
    // keys the b7 lineage-time-travel E2E timed out waiting for the
    // controls under batch churn.
    capabilitiesService.useFallbackCapabilities();
    expect(capabilitiesService.isCapabilityAvailable('lineage.snapshots')).toBe(
      true,
    );
    expect(
      capabilitiesService.isCapabilityAvailable('lineage.change_notifications'),
    ).toBe(true);
  });

  it('keeps the AI schema-matching route reachable (close-test-coverage-gaps 1.2)', () => {
    // routes.tsx wraps /ai/schema-matching in
    // CapabilityRoute capability="ai.schema-matching"; the SPA-side gate
    // resolves from OpenAPI paths and a transient fetch hiccup under
    // batch load bounces the route to /unavailable (the exact failure
    // family previously fixed for marketplace/lineage). The backend
    // endpoint always exists (AIViewSet action, no tenant flag), so this
    // entry is UX-grade fail-open — DE-008 must reach its real flow.
    capabilitiesService.useFallbackCapabilities();
    expect(
      capabilitiesService.isCapabilityAvailable('ai.schema-matching'),
    ).toBe(true);
  });

  it('keeps the developer plugins/portal reachable (close-test-coverage-gaps 1.2)', () => {
    // CapabilityRoute capability="developer.plugins" gates /developer.
    // Server-side enforcement is unchanged (Tenant.developer_enabled →
    // DEVELOPER_DISABLED 403), so the SPA fallback is presentation-only —
    // a transient fetch hiccup must not bounce DE-012/DEV-009 to
    // /unavailable before the backend gets to enforce its own gate.
    capabilitiesService.useFallbackCapabilities();
    expect(
      capabilitiesService.isCapabilityAvailable('developer.plugins'),
    ).toBe(true);
  });
});

describe('capabilitiesService manifest-first path (Phase 273.x hardening)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('derives path capabilities from the manifest and applies the runtime overlay', async () => {
    // Manifest success: NO openapi.json fetch may happen — the 19.7 MB
    // schema must stay off the critical gate path.
    mockGet
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            'social.communities': true,
            'social.ratings': false,
            'ai.natural-language-search': true,
            'auth.register': true,
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: true,
            asset_creation_blocked_reason: null,
            databricks: true,
          },
        },
      });

    const caps = await capabilitiesService.loadCapabilities(true);

    expect(mockGet).toHaveBeenCalledTimes(2); // manifest + runtime snapshot only
    expect(caps['social.communities']?.available).toBe(true);
    expect(caps['social.ratings']?.available).toBe(false);
    expect(caps['ai.natural-language-search']?.available).toBe(true);
    expect(caps['auth.register']?.available).toBe(true);
    // Keys absent from the manifest answer false (same ?? false contract
    // as the OpenAPI derivation).
    expect(caps['baas.api-keys']?.available).toBe(false);
    // Runtime overlay applied on top of the manifest-derived map.
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(true);
  });

  it('falls back to the OpenAPI derivation when the manifest route is unavailable', async () => {
    // Old backend (404 on /capabilities/manifest/): the manifest probe
    // rejects, and the flow continues exactly as before the hardening —
    // openapi.json fetch + runtime snapshot.
    mockGet
      .mockRejectedValueOnce(new Error('404 manifest'))
      .mockResolvedValueOnce({
        data: { paths: { '/api/v1/auth/register/': {} } },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            asset_creation: true,
            asset_creation_blocked_reason: null,
          },
        },
      });

    const caps = await capabilitiesService.loadCapabilities(true);

    expect(mockGet).toHaveBeenCalledTimes(3);
    expect(caps['auth.register']?.available).toBe(true);
  });

  it('fails the lineage runtime keys OPEN when the snapshot fetch fails', async () => {
    // Manifest succeeds, runtime snapshot rejects → runtimeSnapshot is
    // null. Strict keys (databricks) stay fail-CLOSED; the UX-only
    // lineage gates fail OPEN so the time-travel controls survive a
    // transient capabilities hiccup (b7 lineage-time-travel E2E).
    mockGet
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            'social.communities': true,
            'auth.register': true,
          },
        },
      })
      .mockRejectedValueOnce(new Error('runtime snapshot down'));

    await capabilitiesService.loadCapabilities(true);

    expect(capabilitiesService.isCapabilityAvailable('lineage.snapshots')).toBe(
      true,
    );
    expect(
      capabilitiesService.isCapabilityAvailable('lineage.change_notifications'),
    ).toBe(true);
    // Strict opt-in keys still fail closed on a missing snapshot.
    expect(capabilitiesService.isCapabilityAvailable('databricks')).toBe(false);
  });

  it('hides the lineage controls only when the wire explicitly says false', async () => {
    mockGet
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            'social.communities': true,
            'auth.register': true,
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          capabilities: {
            'lineage.snapshots': false,
            'lineage.change_notifications': false,
          },
        },
      });

    await capabilitiesService.loadCapabilities(true);

    expect(capabilitiesService.isCapabilityAvailable('lineage.snapshots')).toBe(
      false,
    );
    expect(
      capabilitiesService.isCapabilityAvailable('lineage.change_notifications'),
    ).toBe(false);
  });
});
