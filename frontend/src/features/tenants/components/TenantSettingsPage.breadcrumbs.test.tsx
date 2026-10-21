/**
 * TenantSettingsPage — 222.2.2 breadcrumbs smoke test.
 *
 * Real page; apiClient HTTP seam auto-mocked so `tenantService` methods
 * resolve. Asserts the Home → Settings → Tenant trail renders once the
 * usage/config loads resolve.
 */
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { TenantSettingsPage } from './TenantSettingsPage';

describe('TenantSettingsPage breadcrumbs', () => {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter>{children}</MemoryRouter>;
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('usage')) {
        // The CURRENT usage payload contract (the component renders
        // storage/API/assets/datasets bars from these fields).
        return Promise.resolve({
          data: {
            tenant_id: 'test-tenant',
            plan_slug: 'pro',
            plan_tier: 'PRO',
            storage_bytes: 1073741824,
            storage_gb: 1,
            api_calls_this_month: 5000,
            asset_count: 45,
            dataset_count: 200,
            plan_limits: {
              max_storage_gb: 100,
              max_api_calls_per_month: 100000,
              max_assets: 100,
              max_datasets: 500,
            },
            usage_percentages: {
              max_storage_gb: 1,
              max_api_calls_per_month: 5,
              max_assets: 45,
              max_datasets: 40,
            },
            quota_warnings: {},
          },
        } as never);
      }
      if (url.includes('config')) {
        return Promise.resolve({
          data: {
            default_dq_profile: 'intake_basic_gx',
            allowed_compliance_regimes: ['GDPR'],
            default_compliance_regimes: ['GDPR'],
            data_retention_days: 365,
            trust_signals_enabled: true,
            versioning_enabled: true,
            workflows_enabled: true,
          },
        } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders Home → Settings → Tenant breadcrumb trail', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    });
    const nav = screen.getByLabelText('Breadcrumb');
    expect(nav).toHaveTextContent(/Home/);
    expect(nav).toHaveTextContent(/Settings/);
    expect(nav).toHaveTextContent(/Tenant/);
  });
});
