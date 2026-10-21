/**
 * Picker → Form → API integration tests (29.69.8.3).
 * Validates the data flow: list API (picker options) → form payload → create API.
 * Real backend only; no mocks.
 *
 * Prerequisites: Backend at VITE_API_BASE_URL; ensure_e2e_user_roles, ensure_e2e_subscription.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { assetService } from '../features/assets/services/assetService';
import { authService } from '../features/auth/services/authService';
import { contractService } from '../features/contracts/services/contractService';
import { datasetService } from '../features/datasets/services/datasetService';
import { fileService } from '../features/files/services/fileService';
import { governanceRetentionService } from '../features/governance/services/governanceRetentionService';
import type { RetentionPolicyCreateRequest } from '../shared/types/governanceRetention';
import { RetentionAction, RetentionPolicyType } from '../shared/types/governanceRetention';

const E2E_EMAIL = 'e2e_test@example.com';
const E2E_PASSWORD = 'TestPass123';

describe('Picker → Form → API integration (real API)', () => {
  beforeEach(async () => {
    authService.clearAuth();
    await authService.login({ email: E2E_EMAIL, password: E2E_PASSWORD });
  });

  afterEach(async () => {
    try {
      await authService.logout();
    } catch {
      authService.clearAuth();
    }
  });

  it('asset list API returns data for AssetPicker', async () => {
    const result = await assetService.list({ page_size: 10 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(typeof result.count).toBe('number');
  });

  it('contract list API returns data for ContractPicker', async () => {
    const result = await contractService.list({ page_size: 10 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(typeof result.count).toBe('number');
  });

  it('dataset list API returns data for DatasetPicker', async () => {
    const result = await datasetService.list({ page_size: 10 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(typeof result.count).toBe('number');
  });

  it('file list API returns data for FilePicker', async () => {
    const result = await fileService.list({ page_size: 10 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(typeof result.count).toBe('number');
  });

  it('retention policy create with asset_id from list API succeeds (picker → form → API)', async () => {
    const assetsResult = await assetService.list({ page_size: 5 });
    const assetId =
      assetsResult.results.length > 0
        ? assetsResult.results[0].id
        : (await assetService.create({ key: 'e2e-picker-int', name: 'E2E Picker Integration', visibility: 'INTERNAL' }))
            .id;

    const payload: RetentionPolicyCreateRequest = {
      name: `e2e-picker-int-${Date.now()}`,
      asset_id: assetId,
      policy_type: RetentionPolicyType.TIME_BASED,
      retention_period_days: 30,
      action: RetentionAction.SOFT_DELETE,
      enabled: true,
    };

    const created = await governanceRetentionService.createPolicy(payload);
    expect(created).toBeDefined();
    expect(created.id).toBeDefined();
    expect(created.asset).toBe(assetId);
    expect(created.name).toBe(payload.name);
  });
});
