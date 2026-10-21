/**
 * TenantSettingsPage component tests (277.B.114).
 *
 * Verifies severity coloring on progress bars, inline upgrade CTA at >=80%,
 * aria attributes, and tab navigation.
 */
import type { HttpClient } from '../../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockGet = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({ get: mockGet }),
    // W5.2 — the tenant reader the capabilities service resolves
    // entries by; these tests exercise the anonymous path.
    getEffectiveTenantId: () => null,
  },
}));

import { apiClient } from '../../../../shared/api/client';
import { TenantSettingsPage } from '../TenantSettingsPage';

async function flushReactQueries(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/** Build a minimal TenantUsage fixture for the usage tab. */
function makeUsage(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    tenant_id: 'test-tenant',
    plan_slug: 'pro',
    plan_tier: 'PRO',
    storage_bytes: 1073741824, // 1 GB
    storage_gb: 1,
    api_calls_this_month: 5000,
    asset_count: 45,
    dataset_count: 200,
    scheduled_ingestion_count: 5,
    scheduled_export_count: 3,
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
    ...overrides,
  };
}

describe('TenantSettingsPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    // Default: return empty config + empty usage (renders loading, then error state)
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({ data: makeUsage() });
      }
      if (typeof url === 'string' && url.includes('me/config')) {
        return Promise.resolve({
          data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
        });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────────

  it('renders without crashing', async () => {
    // Phase T.1 — the previous body asserted nothing (vitest/expect-expect
    // is zero-tolerance); the smoke test now verifies the page actually
    // mounted its shell and default tab.
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();
    expect(screen.getByTestId('tenant-settings-usage')).toBeTruthy();
  });

  it('renders usage tab by default', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();
    const usageSection = screen.queryByTestId('tenant-settings-usage');
    expect(usageSection).toBeTruthy();
  });

  it('shows plan slug and tier', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();
    // The plan line renders "Plan: pro (PRO)" with the slug nested in a
    // <strong> — assert the container rather than the ambiguous text.
    const planEl = screen.getByText(/Plan:/);
    expect(planEl.textContent).toContain('pro');
    expect(planEl.textContent).toContain('PRO');
  });

  // ── Tab navigation ─────────────────────────────────────────────────────

  it('switches to config tab on click', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    // close-test-coverage-gaps 5.4 — the tabs are a WAI-ARIA tablist
    // (role="tab" inside role="tablist"); getByRole('tab') is the
    // correct query for the pattern.
    const configTab = screen.getByRole('tab', { name: 'Configuration' });
    act(() => configTab.click());
    await flushReactQueries();

    const configSection = screen.queryByTestId('tenant-settings-config');
    expect(configSection).toBeTruthy();
  });

  it('switches to compliance tab on click', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const complianceTab = screen.getByRole('tab', { name: 'Compliance' });
    act(() => complianceTab.click());
    await flushReactQueries();

    // Compliance tab should render (even if sub-panels are empty)
    // Just verify the tab switched without crash
    expect(screen.getByTestId('tenant-settings-compliance')).toBeTruthy();
  });

  it('tabs are an ARIA tablist with aria-selected states', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    // The tablist container carries the role + a label; each tab is a
    // role="tab" whose aria-selected reflects the active section.
    const tablist = screen.getByRole('tablist', { name: 'Tenant settings sections' });
    expect(tablist).toBeTruthy();

    const usageTab = screen.getByRole('tab', { name: 'Usage' });
    expect(usageTab.getAttribute('aria-selected')).toBe('true');

    const configTab = screen.getByRole('tab', { name: 'Configuration' });
    expect(configTab.getAttribute('aria-selected')).toBe('false');
  });

  // ── Progress bar severity colors ───────────────────────────────────────

  it('renders progress bars with role="progressbar"', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const bars = screen.getAllByRole('progressbar');
    expect(bars.length).toBeGreaterThanOrEqual(2);
  });

  it('progress bars have aria-valuenow/min/max', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const bars = screen.getAllByRole('progressbar');
    for (const bar of bars) {
      expect(bar.getAttribute('aria-valuenow')).toBeTruthy();
      expect(bar.getAttribute('aria-valuemin')).toBe('0');
      expect(bar.getAttribute('aria-valuemax')).toBe('100');
    }
  });

  it('progress bars have aria-label with usage percentage', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const bars = screen.getAllByRole('progressbar');
    for (const bar of bars) {
      const label = bar.getAttribute('aria-label');
      expect(label).toBeTruthy();
      expect(label).toContain('usage');
    }
  });

  it('normal usage (<80%) uses normal severity class', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    // At 5%, the API calls bar should be normal
    const normalBars = document.querySelectorAll('.tenant-metric-bar-fill--normal');
    expect(normalBars.length).toBeGreaterThan(0);
  });

  it('warn usage (>80%) uses warn severity class', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({
            usage_percentages: {
              max_storage_gb: 85,    // >80% → warn (the single warn bar)
              max_api_calls_per_month: 50,
              max_assets: 40,        // below 80 — stays out of warn
              max_datasets: 10,
            },
          }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const warnBars = document.querySelectorAll('.tenant-metric-bar-fill--warn');
    expect(warnBars.length).toBe(1);
  });

  it('danger usage (>95%) uses danger severity class', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({
            usage_percentages: {
              max_storage_gb: 85,
              max_api_calls_per_month: 50,
              max_assets: 96,        // >95% → danger
              max_datasets: 10,
            },
          }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const dangerBars = document.querySelectorAll('.tenant-metric-bar-fill--danger');
    expect(dangerBars.length).toBe(1);
  });

  // ── Upgrade CTA ────────────────────────────────────────────────────────

  it('shows upgrade CTA when any limit >= 80%', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({
            usage_percentages: {
              max_storage_gb: 85,
              max_api_calls_per_month: 50,
              max_assets: 90,
              max_datasets: 10,
            },
          }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const cta = screen.queryByTestId('usage-upgrade-cta');
    expect(cta).toBeTruthy();
    if (cta) {
      expect(cta.textContent).toContain('Upgrade plan');
    }
  });

  it('does not show upgrade CTA when all limits < 80%', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const cta = screen.queryByTestId('usage-upgrade-cta');
    expect(cta).toBeFalsy();
  });

  it('upgrade CTA links to /settings/billing', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({
            usage_percentages: {
              max_storage_gb: 85,
              max_api_calls_per_month: 50,
              max_assets: 90,
              max_datasets: 10,
            },
          }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const link = screen.queryByText(/upgrade plan/i);
    expect(link).toBeTruthy();
    if (link) {
      expect(link.closest('a')?.getAttribute('href')).toBe('/settings/billing');
    }
  });

  // ── Edge cases ─────────────────────────────────────────────────────────

  it('handles null usage_percentages gracefully', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({ usage_percentages: null }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    // Should not crash — progress bars just don't render or show 0
    const usageSection = screen.queryByTestId('tenant-settings-usage');
    expect(usageSection).toBeTruthy();
  });

  it('handles missing plan_limits gracefully', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({ plan_limits: {}, usage_percentages: {} }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const usageSection = screen.queryByTestId('tenant-settings-usage');
    expect(usageSection).toBeTruthy();
  });

  it('handles zero-values gracefully (no division by zero)', async () => {
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('me/usage')) {
        return Promise.resolve({
          data: makeUsage({
            storage_bytes: 0,
            storage_gb: 0,
            api_calls_this_month: 0,
            asset_count: 0,
            dataset_count: 0,
            usage_percentages: {
              max_storage_gb: 0,
              max_api_calls_per_month: 0,
              max_assets: 0,
              max_datasets: 0,
            },
          }),
        });
      }
      return Promise.resolve({
        data: { tenant_id: 'test-tenant', created_at: '2026-01-01', updated_at: '2026-01-01' },
      });
    });

    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    const usageSection = screen.queryByTestId('tenant-settings-usage');
    expect(usageSection).toBeTruthy();
  });

  it('shows all four metric labels', async () => {
    render(<TenantSettingsPage />, { wrapper: Wrapper });
    await flushReactQueries();

    expect(screen.getByText('Storage')).toBeTruthy();
    expect(screen.getByText('API calls (this month)')).toBeTruthy();
    expect(screen.getByText('Assets')).toBeTruthy();
    expect(screen.getByText('Datasets')).toBeTruthy();
  });
});
