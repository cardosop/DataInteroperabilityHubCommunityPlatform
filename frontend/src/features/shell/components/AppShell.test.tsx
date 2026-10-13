/**
 * AppShell mobile nav tests — Phase 224.5.
 *
 * Exercises the sidebar-open state wiring between AppShell, Header and
 * Sidebar: hamburger toggles visibility, backdrop click closes, Escape closes.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { capabilitiesService } from '../../capabilities/services/capabilitiesService';
import { fullModeOpenApiSchema, isOpenApiUrl } from '../../../test/openApiSchemaMock';

import { useAuthStore } from '../../auth/store/authStore';
import { AppShell } from './AppShell';

function setUser() {
  useAuthStore.setState({
    user: {
      id: 'u1',
      email: 'u@example.com',
      name: 'U',
      roles: ['TENANT_ADMIN'],
      tenant_id: 't1',
      is_active: true,
    },
    active_tenant_id: null,
    isAuthenticated: true,
    isLoading: false,
    error: null,
  });
}

function Wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          {/* Catch-all keeps the shell mounted while a nav click changes
              the pathname (the AppShell closes the mobile overlay on
              pathname change). */}
          <Route path="*" element={children as never} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AppShell mobile sidebar', () => {
  beforeEach(async () => {
    setUser();
    // 313.H.4 — the Header tenant switcher fetches /tenants (array) and
    // the capabilities service fetches the OpenAPI schema; both must
    // return realistic shapes (a bare `{}` broke the switcher with
    // "tenants.find is not a function").
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (isOpenApiUrl(url)) {
        return Promise.resolve({ data: fullModeOpenApiSchema() } as never);
      }
      if (url.includes('/tenants')) {
        return Promise.resolve({ data: [] } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });
    // 313.H.4 — prime the singleton beyond its 5-minute cache so the
    // full-mode schema (not a prior test's empty one) is what renders.
    await capabilitiesService.loadCapabilities(true);
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

  it('renders the hamburger toggle in the header', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    expect(screen.getByTestId('sidebar-toggle')).toBeInTheDocument();
  });

  it('sidebar is closed by default (no open state on shell)', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    const shell = screen.getByTestId('app-shell');
    expect(shell).toHaveAttribute('data-sidebar-open', 'false');
    expect(screen.queryByTestId('sidebar-backdrop')).not.toBeInTheDocument();
  });

  it('clicking the hamburger opens the sidebar and renders a backdrop', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('app-shell')).toHaveAttribute(
      'data-sidebar-open',
      'true',
    );
    expect(screen.getByTestId('sidebar-backdrop')).toBeInTheDocument();
  });

  it('hamburger updates aria-expanded to reflect state', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    const toggle = screen.getByTestId('sidebar-toggle');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });

  it('clicking the backdrop closes the sidebar', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    fireEvent.click(screen.getByTestId('sidebar-backdrop'));
    expect(screen.getByTestId('app-shell')).toHaveAttribute(
      'data-sidebar-open',
      'false',
    );
  });

  it('pressing Escape closes an open sidebar', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByTestId('app-shell')).toHaveAttribute(
      'data-sidebar-open',
      'false',
    );
  });

  it('navigating via a sidebar link closes the mobile overlay', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    // Click a link that CHANGES the pathname — the AppShell closes the
    // overlay on pathname change; clicking the current path ('/') is a
    // no-op navigation and correctly leaves the overlay open.
    const contractsLink = screen
      .getByRole('navigation', { name: /main navigation/i })
      .querySelector('a[href="/contracts"]');
    expect(contractsLink).toBeTruthy();
    fireEvent.click(contractsLink!);
    expect(screen.getByTestId('app-shell')).toHaveAttribute(
      'data-sidebar-open',
      'false',
    );
  });
});

describe('AppShell CommandPalette MVP filtering (Track A PR 4)', () => {
  beforeEach(async () => {
    setUser();
    vi.stubEnv('VITE_MVP_MODE', 'true');
    // 313.H.4 — full-mode schema so capability gating is neutral; the
    // MVP filter is the only variable under test.
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (isOpenApiUrl(url)) {
        return Promise.resolve({ data: fullModeOpenApiSchema() } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });
    await capabilitiesService.loadCapabilities(true);
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

  it('CommandPalette pages list does NOT include non-MVP routes when VITE_MVP_MODE=true', () => {
    render(
      <Wrapper>
        <AppShell />
      </Wrapper>,
    );
    // Open the palette via Ctrl+K (the canonical shortcut).
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    // Once open, palette options are usually rendered as buttons or links
    // with the page label as text. Non-MVP labels must be absent.
        // 'Search' deliberately absent — Phase 273.1 made /search permanently MVP-in-scope.
    const HIDDEN_LABELS = ['Data Mesh', 'BaaS', 'ML', 'Observability', 'Developer'];
    for (const label of HIDDEN_LABELS) {
      // Sidebar may be closed (mobile width) so the only place the label
      // could appear under MVP mode is the palette. Either way, it should
      // be absent.
      expect(
        screen.queryAllByText(label).length,
        `Palette must not list "${label}" under VITE_MVP_MODE=true`,
      ).toBe(0);
    }
  });
});
