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

    expect(mockGet).toHaveBeenCalledTimes(3);
    expect(caps['auth.register']?.available).toBe(true);
    // Runtime-snapshot fetch landed too — assert the reason getter
    // surfaces the stubbed value.
    expect(capabilitiesService.getAssetCreationBlockedReason()).toBeNull();
    expect(capabilitiesService.isAssetCreationAllowedRuntime()).toBe(true);
  });

  it('exposes the onboarding-incomplete reason from the runtime snapshot', async () => {
    // Phase 250.6.D.2 — pin the reason discriminator pass-through.
    mockGet
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
});
