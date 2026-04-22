/**
 * Sidebar badge-rendering tests — 222.1.
 *
 * Uses the real Sidebar, real useUnreadBadgeCounts, real useAuthStore, and
 * real React Query; only the HTTP layer (apiClient) is auto-mocked via the
 * shared `src/shared/api/__mocks__/client.ts` seam so the hook's network call
 * can be steered per-test.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { Sidebar } from './Sidebar';

function setUser(opts: { roles: string[]; is_platform_admin?: boolean }) {
  useAuthStore.setState({
    user: {
      id: 'u1',
      email: 'u@example.com',
      name: 'U',
      roles: opts.roles,
      tenant_id: 't1',
      is_active: true,
      is_platform_admin: opts.is_platform_admin,
    },
    active_tenant_id: null,
    isAuthenticated: true,
    isLoading: false,
    error: null,
  });
}

describe('Sidebar governance badge', () => {
  let queryClient: QueryClient;

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
      defaultOptions: { queries: { retry: false } },
    });
  });

  afterEach(() => {
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it('renders a red badge next to Governance for TENANT_ADMIN when count > 0', async () => {
    setUser({ roles: ['TENANT_ADMIN'] });
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('pending-count')) {
        return Promise.resolve({ data: { count: 3 } } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });

    render(<Sidebar />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('nav-badge-/governance')).toHaveTextContent('3');
    });
  });

  it('does not render a badge when count is 0', async () => {
    setUser({ roles: ['TENANT_ADMIN'] });
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('pending-count')) {
        return Promise.resolve({ data: { count: 0 } } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });

    render(<Sidebar />, { wrapper: Wrapper });

    // Let the query resolve
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId('nav-badge-/governance')).toBeNull();
  });

  it('caps large counts at 99+', async () => {
    setUser({ roles: ['PLATFORM_ADMIN'], is_platform_admin: true });
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('pending-count')) {
        return Promise.resolve({ data: { count: 250 } } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });

    render(<Sidebar />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('nav-badge-/governance')).toHaveTextContent('99+');
    });
  });

  it('never shows the Governance item (and therefore no badge) for non-admins', async () => {
    setUser({ roles: ['DATA_CONSUMER'] });
    const getMock = vi.mocked(apiClient.getClient().get);
    getMock.mockResolvedValue({ data: {} } as never);

    render(<Sidebar />, { wrapper: Wrapper });

    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText('Governance')).toBeNull();
    expect(screen.queryByTestId('nav-badge-/governance')).toBeNull();
    // Hook must short-circuit before calling the admin-only endpoint.
    const calledPendingCount = getMock.mock.calls.some(
      (args) => typeof args[0] === 'string' && args[0].includes('pending-count'),
    );
    expect(calledPendingCount).toBe(false);
  });
});

describe('Sidebar MVP mode filtering (Track A PR 4)', () => {
  let queryClient: QueryClient;

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
      defaultOptions: { queries: { retry: false } },
    });
    // Render as a full-access user so any hidden item is hidden by the
    // MVP filter, not by capability/role gating.
    setUser({ roles: ['TENANT_ADMIN', 'PLATFORM_ADMIN'], is_platform_admin: true });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({ data: {} } as never);
    vi.stubEnv('VITE_MVP_MODE', 'true');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it('hides every label whose path is in NON_MVP_PATHS', async () => {
    render(<Sidebar />, { wrapper: Wrapper });
    // Allow any one tick of rendering for the capabilities hook to settle.
    await new Promise((r) => setTimeout(r, 20));

    // Labels from navItems.ts that map to NON_MVP_PATHS:
    const HIDDEN_LABELS = [
      'Data Mesh',
      'Virtualization',
      'Search',
      'Communities',
      'BaaS',
      'ML',
      'Observability',
      'Developer',
      'Transformation',
    ];
    for (const label of HIDDEN_LABELS) {
      expect(
        screen.queryByText(label),
        `Sidebar label "${label}" should be hidden under VITE_MVP_MODE=true`,
      ).toBeNull();
    }
  });

  it('still shows MVP-scope items including /semantic', async () => {
    render(<Sidebar />, { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));

    // Items expected to remain visible — Semantic is the load-bearing
    // exception (see docs/mvp-gate.md).
    const VISIBLE_LABELS = ['Assets', 'Contracts', 'Datasets', 'Semantic'];
    for (const label of VISIBLE_LABELS) {
      expect(
        screen.getAllByText(label).length,
        `Sidebar label "${label}" should be visible under VITE_MVP_MODE=true`,
      ).toBeGreaterThanOrEqual(1);
    }
  });
});
