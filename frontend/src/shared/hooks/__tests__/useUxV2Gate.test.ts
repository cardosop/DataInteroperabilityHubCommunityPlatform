/**
 * useUxV2Gate unit test — 278.P.2
 *
 * Verifies the gate returns expected values based on mocked capability state.
 */
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useUxV2Gate } from '../useUxV2Gate';

vi.mock('../useCapabilities', () => ({
  useCapabilities: vi.fn(),
}));

import { useCapabilities } from '../useCapabilities';

describe('useUxV2Gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns enabled=true when ux_v2 capability is true', () => {
    vi.mocked(useCapabilities).mockReturnValue({
      isCapabilityAvailable: vi.fn((key: string) => key === 'ux_v2'),
      isLoading: false,
      capabilities: { ux_v2: true },
      openApiSchema: null as never,
      isFeatureAvailable: vi.fn(),
      isPathAvailable: vi.fn(),
      isAnyCapabilityAvailable: vi.fn(),
      isAssetCreationEnabled: vi.fn(),
      isOPSDisabled: vi.fn(),
      isOnboardingIncomplete: vi.fn(),
      isDataQualityEnabled: vi.fn(),
      isDataQualityAdvancedEnabled: vi.fn(),
      refreshCapabilities: vi.fn(),
    } as never);

    const { result } = renderHook(() => useUxV2Gate());
    expect(result.current.enabled).toBe(true);
    expect(result.current.isLoading).toBe(false);
  });

  it('returns enabled=false when ux_v2 capability is false', () => {
    vi.mocked(useCapabilities).mockReturnValue({
      isCapabilityAvailable: vi.fn(() => false),
      isLoading: false,
      capabilities: { ux_v2: false },
      openApiSchema: null as never,
      isFeatureAvailable: vi.fn(),
      isPathAvailable: vi.fn(),
      isAnyCapabilityAvailable: vi.fn(),
      isAssetCreationEnabled: vi.fn(),
      isOPSDisabled: vi.fn(),
      isOnboardingIncomplete: vi.fn(),
      isDataQualityEnabled: vi.fn(),
      isDataQualityAdvancedEnabled: vi.fn(),
      refreshCapabilities: vi.fn(),
    } as never);

    const { result } = renderHook(() => useUxV2Gate());
    expect(result.current.enabled).toBe(false);
  });

  it('returns isLoading=true when capabilities are loading', () => {
    vi.mocked(useCapabilities).mockReturnValue({
      isCapabilityAvailable: vi.fn(() => false),
      isLoading: true,
      capabilities: {},
      openApiSchema: null as never,
      isFeatureAvailable: vi.fn(),
      isPathAvailable: vi.fn(),
      isAnyCapabilityAvailable: vi.fn(),
      isAssetCreationEnabled: vi.fn(),
      isOPSDisabled: vi.fn(),
      isOnboardingIncomplete: vi.fn(),
      isDataQualityEnabled: vi.fn(),
      isDataQualityAdvancedEnabled: vi.fn(),
      refreshCapabilities: vi.fn(),
    } as never);

    const { result } = renderHook(() => useUxV2Gate());
    expect(result.current.isLoading).toBe(true);
  });

  it('returns enabled=false when ux_v2 key is absent from capabilities', () => {
    vi.mocked(useCapabilities).mockReturnValue({
      isCapabilityAvailable: vi.fn(() => false),
      isLoading: false,
      capabilities: { data_quality: true },
      openApiSchema: null as never,
      isFeatureAvailable: vi.fn(),
      isPathAvailable: vi.fn(),
      isAnyCapabilityAvailable: vi.fn(),
      isAssetCreationEnabled: vi.fn(),
      isOPSDisabled: vi.fn(),
      isOnboardingIncomplete: vi.fn(),
      isDataQualityEnabled: vi.fn(),
      isDataQualityAdvancedEnabled: vi.fn(),
      refreshCapabilities: vi.fn(),
    } as never);

    const { result } = renderHook(() => useUxV2Gate());
    expect(result.current.enabled).toBe(false);
  });
});
