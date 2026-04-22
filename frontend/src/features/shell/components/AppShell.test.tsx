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
          <Route path="/" element={children as never} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AppShell mobile sidebar', () => {
  beforeEach(() => {
    setUser();
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
    const firstLink = screen.getByRole('navigation', { name: /main navigation/i })
      .querySelector('a');
    expect(firstLink).toBeTruthy();
    fireEvent.click(firstLink!);
    expect(screen.getByTestId('app-shell')).toHaveAttribute(
      'data-sidebar-open',
      'false',
    );
  });
});

describe('AppShell CommandPalette MVP filtering (Track A PR 4)', () => {
  beforeEach(() => {
    setUser();
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
    const HIDDEN_LABELS = ['Data Mesh', 'BaaS', 'ML', 'Search', 'Observability', 'Developer'];
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
