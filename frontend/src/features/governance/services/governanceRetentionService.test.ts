/**
 * Governance Retention Service Tests
 * Tests for retention policy service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { AxiosInstance } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  RetentionPolicy,
  RetentionPolicyCreateRequest,
  RetentionPolicyListFilters,
  RetentionPolicyUpdateRequest,
} from '../../../shared/types/governanceRetention';
import { RetentionAction, RetentionPolicyType } from '../../../shared/types/governanceRetention';

// Mock axios at module level - this allows apiClient to use real methods
// but intercepts HTTP calls for testing
vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

import axios from 'axios';
import { apiClient } from '../../../shared/api/client';
import { governanceRetentionService } from './governanceRetentionService';

// Get the mock instance from axios.create
const mockAxiosCreate = vi.mocked(axios.create);

describe('governanceRetentionService', () => {
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via axios.create mock
    mockAxiosInstance = realClient;
  });

  describe('listPolicies', () => {
    it('should list retention policies with filters', async () => {
      const mockResponse = {
        data: {
          count: 2,
          page: 1,
          page_size: 20,
          total_pages: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'policy-1',
              name: 'Policy 1',
              policy_type: RetentionPolicyType.TIME_BASED,
              enabled: true,
            },
            {
              id: 'policy-2',
              name: 'Policy 2',
              policy_type: RetentionPolicyType.EVENT_BASED,
              enabled: false,
            },
          ] as RetentionPolicy[],
        },
      };

      // Mock the get method on the axios instance
      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const filters: RetentionPolicyListFilters = {
        page: 1,
        page_size: 20,
        asset_id: 'asset-123',
        enabled: true,
      };

      const result = await governanceRetentionService.listPolicies(filters);

      // Verify the service called apiClient.getClient().get() with correct URL
      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'governance/retention-policies/?page=1&page_size=20&asset_id=asset-123&enabled=true'
      );
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      // Verify code and details are preserved in response
      expect(result.results[0].id).toBe('policy-1');
      expect(result.results[0].policy_type).toBe(RetentionPolicyType.TIME_BASED);
    });

    it('should list retention policies without filters', async () => {
      const mockResponse = {
        data: {
          count: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
          next: null,
          previous: null,
          results: [],
        },
      };

      // Mock the get method on the axios instance
      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const result = await governanceRetentionService.listPolicies();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'governance/retention-policies/'
      );
      expect(result.count).toBe(0);
      expect(result.results).toHaveLength(0);
    });
  });

  describe('getPolicy', () => {
    it('should get a retention policy by ID', async () => {
      const mockPolicy: RetentionPolicy = {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Test Policy',
        description: 'Test description',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: RetentionPolicyType.TIME_BASED,
        retention_period_days: 30,
        event_trigger: null,
        action: RetentionAction.SOFT_DELETE,
        grace_period_days: 30,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      (mockAxiosInstance.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: mockPolicy,
      });

      const result = await governanceRetentionService.getPolicy('policy-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'governance/retention-policies/policy-1/'
      );
      expect(result.id).toBe('policy-1');
      expect(result.name).toBe('Test Policy');
      expect(result.policy_type).toBe(RetentionPolicyType.TIME_BASED);
    });
  });

  describe('createPolicy', () => {
    it('should create a retention policy', async () => {
      const createRequest: RetentionPolicyCreateRequest = {
        name: 'New Policy',
        description: 'New policy description',
        asset_id: 'asset-1',
        policy_type: RetentionPolicyType.TIME_BASED,
        retention_period_days: 30,
        action: RetentionAction.SOFT_DELETE,
        grace_period_days: 30,
        enabled: true,
      };

      const mockCreatedPolicy: RetentionPolicy = {
        id: 'policy-new',
        tenant: 'tenant-1',
        name: 'New Policy',
        description: 'New policy description',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: RetentionPolicyType.TIME_BASED,
        retention_period_days: 30,
        event_trigger: null,
        action: RetentionAction.SOFT_DELETE,
        grace_period_days: 30,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockCreatedPolicy,
      });

      const result = await governanceRetentionService.createPolicy(createRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'governance/retention-policies/',
        createRequest
      );
      expect(result.id).toBe('policy-new');
      expect(result.name).toBe('New Policy');
    });
  });

  describe('updatePolicy', () => {
    it('should update a retention policy', async () => {
      const updateRequest: RetentionPolicyUpdateRequest = {
        id: 'policy-1',
        name: 'Updated Policy',
        retention_period_days: 60,
      };

      const mockUpdatedPolicy: RetentionPolicy = {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Updated Policy',
        description: 'Test description',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: RetentionPolicyType.TIME_BASED,
        retention_period_days: 60,
        event_trigger: null,
        action: RetentionAction.SOFT_DELETE,
        grace_period_days: 30,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.patch).mockResolvedValue({
        data: mockUpdatedPolicy,
      });

      const result = await governanceRetentionService.updatePolicy(updateRequest);

      expect(vi.mocked(mockAxiosInstance.patch)).toHaveBeenCalledWith(
        'governance/retention-policies/policy-1/',
        { name: 'Updated Policy', retention_period_days: 60 }
      );
      expect(result.id).toBe('policy-1');
      expect(result.name).toBe('Updated Policy');
      expect(result.retention_period_days).toBe(60);
    });
  });

  describe('deletePolicy', () => {
    it('should delete a retention policy', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      });

      await governanceRetentionService.deletePolicy('policy-1');

      expect(vi.mocked(mockAxiosInstance.delete)).toHaveBeenCalledWith(
        'governance/retention-policies/policy-1/'
      );
    });
  });
});
