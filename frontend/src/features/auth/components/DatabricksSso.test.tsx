/**
 * Pins for the 0b.12 SSO surfaces: the login button (tenant hint +
 * chooser/direct-redirect), the workspace chooser modal, and the session
 * countdown banner.
 *
 * The service layer is stubbed at the module boundary (the wire contract
 * is pinned by the backend suite against the real API); window.location
 * assignment is pinned via a stub.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ContinueWithDatabricksButton } from './ContinueWithDatabricksButton';

vi.mock('../../databricks/services/databricksSsoService', () => ({
  ssoWorkspaces: vi.fn(),
  ssoLoginUrl: vi.fn(),
  ssoSession: vi.fn(),
}));

import {
  ssoLoginUrl,
  ssoSession,
  ssoWorkspaces,
} from '../../databricks/services/databricksSsoService';

const mockWorkspaces = vi.mocked(ssoWorkspaces);
const mockLoginUrl = vi.mocked(ssoLoginUrl);
const mockSession = vi.mocked(ssoSession);

beforeEach(() => {
  vi.clearAllMocks();
  // Timer-leak guard: a timed-out fake-timer test would otherwise freeze
  // every sibling test's polling (findBy*/waitFor never fire).
  vi.useRealTimers();
});

describe('ContinueWithDatabricksButton', () => {
  it('renders nothing without a tenant hint', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <ContinueWithDatabricksButton />
      </MemoryRouter>
    );
    expect(screen.queryByTestId('databricks-sso-button')).not.toBeInTheDocument();
  });

  it('redirects directly when the tenant has exactly one workspace', async () => {
    mockWorkspaces.mockResolvedValue([
      { id: 'w1', name: 'prod', host: 'dbc-1.cloud.databricks.com', cloud: 'AWS' },
    ]);
    mockLoginUrl.mockResolvedValue({ login_url: 'https://dbc-1.cloud.databricks.com/oidc/v1/authorize' });
    const assign = vi.fn();
    vi.stubGlobal('location', { assign, origin: 'https://hub.example.com' });

    render(
      <MemoryRouter initialEntries={['/login?tenant_id=t1']}>
        <ContinueWithDatabricksButton />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByTestId('databricks-sso-button'));
    expect(mockLoginUrl).toHaveBeenCalledWith(
      't1',
      'w1',
      'https://hub.example.com/auth/databricks/callback'
    );
    expect(assign).toHaveBeenCalledWith(
      'https://dbc-1.cloud.databricks.com/oidc/v1/authorize'
    );
    vi.unstubAllGlobals();
  });

  it('opens the chooser for multi-workspace tenants', async () => {
    mockWorkspaces.mockResolvedValue([
      { id: 'w1', name: 'prod', host: 'dbc-1.cloud.databricks.com', cloud: 'AWS' },
      { id: 'w2', name: 'dev', host: 'dbc-2.cloud.databricks.com', cloud: 'AWS' },
    ]);
    render(
      <MemoryRouter initialEntries={['/login?tenant_id=t1']}>
        <ContinueWithDatabricksButton />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByTestId('databricks-sso-button'));
    expect(await screen.findByTestId('databricks-chooser')).toBeInTheDocument();
    expect(screen.getByText(/prod/)).toBeInTheDocument();
    expect(screen.getByText(/dev/)).toBeInTheDocument();
  });

  it('surfaces the flag-disabled code when the tenant gate rejects', async () => {
    const { DatabricksApiError } = await import(
      '../../databricks/services/databricksService'
    );
    mockWorkspaces.mockRejectedValue(
      new DatabricksApiError('Sign-in with Databricks is disabled', 'DATABRICKS_SSO_DISABLED')
    );
    render(
      <MemoryRouter initialEntries={['/login?tenant_id=t1']}>
        <ContinueWithDatabricksButton />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByTestId('databricks-sso-button'));
    expect(await screen.findByText(/DATABRICKS_SSO_DISABLED/)).toBeInTheDocument();
  });
});

describe('SessionCountdownBanner', () => {
  it('shows the countdown when the session endpoint reports an active window', async () => {
    const { SessionCountdownBanner } = await import('./SessionCountdownBanner');
    const { useAuthStore } = await import('../store/authStore');
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: 'u1', email: 'u@example.com', name: 'U' },
    });
    mockSession.mockResolvedValue({
      countdown: { active: true, seconds_remaining: 299 },
      hub_reauth_deadline: '2026-09-09T12:00:00Z',
    });

    render(<SessionCountdownBanner />);
    expect(await screen.findByTestId('databricks-countdown-banner')).toBeInTheDocument();
    expect(screen.getByTestId('databricks-countdown-seconds')).toHaveTextContent('5');
    useAuthStore.setState({ user: null, isAuthenticated: false });
  });

  it('hides when no countdown is active', async () => {
    const { SessionCountdownBanner } = await import('./SessionCountdownBanner');
    const { useAuthStore } = await import('../store/authStore');
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: 'u1', email: 'u@example.com', name: 'U' },
    });
    mockSession.mockResolvedValue({
      countdown: { active: false, seconds_remaining: null },
      hub_reauth_deadline: '2026-09-09T12:00:00Z',
    });

    render(<SessionCountdownBanner />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId('databricks-countdown-banner')).not.toBeInTheDocument();
    useAuthStore.setState({ user: null, isAuthenticated: false });
  });

  it('re-polls the session endpoint on the 30s interval', async () => {
    // shouldAdvanceTime: the initial findByTestId poll must fire under
    // fake timers; the 30s interval itself is advanced explicitly below.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { SessionCountdownBanner } = await import('./SessionCountdownBanner');
      const { useAuthStore } = await import('../store/authStore');
      useAuthStore.setState({
        isAuthenticated: true,
        user: { id: 'u1', email: 'u@example.com', name: 'U' },
      });
      mockSession.mockResolvedValue({
        countdown: { active: true, seconds_remaining: 299 },
        hub_reauth_deadline: '2026-09-09T12:00:00Z',
      });

      render(<SessionCountdownBanner />);
      expect(
        await screen.findByTestId('databricks-countdown-banner')
      ).toBeInTheDocument();
      expect(mockSession).toHaveBeenCalledTimes(1);

      // Advance one full poll interval: the banner re-polls the session
      // endpoint and keeps the countdown surface alive.
      await vi.advanceTimersByTimeAsync(30_000);
      expect(mockSession).toHaveBeenCalledTimes(2);
      expect(
        screen.getByTestId('databricks-countdown-banner')
      ).toBeInTheDocument();
      useAuthStore.setState({ user: null, isAuthenticated: false });
    } finally {
      vi.useRealTimers();
    }
  });

  it('transient poll failure hides the banner but never the session', async () => {
    const { SessionCountdownBanner } = await import('./SessionCountdownBanner');
    const { useAuthStore } = await import('../store/authStore');
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: 'u1', email: 'u@example.com', name: 'U' },
    });
    mockSession.mockRejectedValue(new Error('network blip'));

    render(<SessionCountdownBanner />);
    await new Promise((r) => setTimeout(r, 50));
    expect(
      screen.queryByTestId('databricks-countdown-banner')
    ).not.toBeInTheDocument();
    // A Databricks session-poll failure never logs the user out of the
    // Hub — the store keeps the authenticated session.
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    useAuthStore.setState({ user: null, isAuthenticated: false });
  });

  it('exposes the countdown as a live status region for screen readers', async () => {
    const { SessionCountdownBanner } = await import('./SessionCountdownBanner');
    const { useAuthStore } = await import('../store/authStore');
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: 'u1', email: 'u@example.com', name: 'U' },
    });
    mockSession.mockResolvedValue({
      countdown: { active: true, seconds_remaining: 299 },
      hub_reauth_deadline: '2026-09-09T12:00:00Z',
    });

    render(<SessionCountdownBanner />);
    const banner = await screen.findByRole('status');
    expect(banner).toHaveTextContent('5');
    useAuthStore.setState({ user: null, isAuthenticated: false });
  });
});
