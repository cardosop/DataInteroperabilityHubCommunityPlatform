/**
 * useCapabilities hook tests.
 * Real useCapabilities and capabilitiesService; only API client mocked.
 * Scenarios: success (capabilities loaded), error (fallback capabilities), loading then success.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useCapabilities } from './useCapabilities';
import { apiClient } from '../api/client';

vi.mock('../api/client');

const mockClient = apiClient.getClient();

describe('useCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (typeof localStorage !== 'undefined') {
      localStorage.clear();
    }
  });

  it('should load capabilities on success', async () => {
    const openApiPaths: Record<string, unknown> = {
      '/api/v1/auth/register/': {},
      '/api/v1/auth/password-reset/': {},
    };
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { paths: openApiPaths },
    });

    const { result } = renderHook(() => useCapabilities());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.capabilities).toBeDefined();
    expect(typeof result.current.isCapabilityAvailable).toBe('function');
    expect(typeof result.current.getCapability).toBe('function');
    expect(result.current.isCapabilityAvailable('auth.register')).toBe(true);
  });

  it('should use fallback capabilities on error', async () => {
    vi.mocked(mockClient.get).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useCapabilities());

    // Service retries once after 1500ms; wait long enough for both attempts to complete
    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2500 }
    );

    // On error the service fails open: returns auth fallback, not empty (so auth routes stay usable)
    expect(result.current.capabilities).toBeDefined();
    expect(result.current.isCapabilityAvailable('auth.register')).toBe(true);
    expect(result.current.isCapabilityAvailable('auth.password-reset')).toBe(true);
  });

  it('should return capability via getCapability when available', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { paths: { '/api/v1/auth/register/': {} } },
    });

    const { result } = renderHook(() => useCapabilities());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const cap = result.current.getCapability('auth.register');
    expect(cap).not.toBeNull();
    expect(cap?.available).toBe(true);
    expect(cap?.name).toBeDefined();
  });
});
