/**
 * 285.13.11.2 — Pricing page API service.
 */
import { apiClient } from '../../shared/api/client';
import type { PublicPricingResponse } from '../../shared/types/billing';

const BASE = '/api/v1';

export async function fetchPublicPricing(): Promise<PublicPricingResponse> {
  const resp = await apiClient.getClient().get<PublicPricingResponse>(
    `${BASE}/plans/public/`,
  );
  return resp.data;
}
