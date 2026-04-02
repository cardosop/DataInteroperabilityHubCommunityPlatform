/**
 * useSupportedContractVersions
 *
 * Fetches the list of supported ODCS and ODPS versions from the API.
 * The result is cached with staleTime: Infinity because the version
 * list is effectively static between deploys.
 *
 * Falls back to the hardcoded ODCS_EXPORT_VERSIONS if the API is
 * unavailable (graceful degradation).
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../../shared/api/client';
import { ODCS_EXPORT_VERSIONS } from '../../../shared/types/contracts';

/** Shape returned by GET /api/v1/contracts/supported-versions/ */
export interface SupportedVersions {
  odcs: string[];
  odps: string[];
}

/** Default fallback when the endpoint is unavailable */
const FALLBACK: SupportedVersions = {
  odcs: [...ODCS_EXPORT_VERSIONS],
  odps: ['1.x', '2.x', '3.x', '4.0', '4.1', '4.2', 'bitol-0.9.0', 'bitol-1.0.0'],
};

async function fetchSupportedVersions(): Promise<SupportedVersions> {
  try {
    const response = await apiClient.getClient().get<SupportedVersions>(
      'contracts/supported-versions/',
    );
    return response.data;
  } catch {
    // Endpoint may not exist yet (26.8.1 backend) — return fallback
    return FALLBACK;
  }
}

/**
 * React Query hook for supported contract versions.
 *
 * @returns Query result with `data: SupportedVersions`
 *
 * @example
 * ```tsx
 * const { data: versions } = useSupportedContractVersions();
 * // versions.odcs → ["2.2.2", "3.0.0", "3.0.1", "3.0.2", "3.1.0"]
 * // versions.odps → ["1.x", "2.x", ..., "bitol-1.0.0"]
 * ```
 */
export function useSupportedContractVersions() {
  return useQuery({
    queryKey: ['contracts', 'supported-versions'],
    queryFn: fetchSupportedVersions,
    staleTime: Infinity,         // static between deploys
    gcTime: 1000 * 60 * 60 * 24, // keep in cache for 24h
    placeholderData: FALLBACK,    // show fallback while loading
  });
}
