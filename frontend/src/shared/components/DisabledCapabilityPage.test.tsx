/**
 * Phase 250.6.A.5 TDD pin for `<DisabledCapabilityPage>`.
 *
 * Verifies the wire contract used by `<CapabilityRoute>`:
 *
 * 1. Reads the capability name from `location.state.capability` when
 *    rendered as a redirect target (no explicit prop).
 * 2. Accepts an explicit `capability` prop for direct rendering
 *    (overrides location.state — useful for tests + non-redirect mounts).
 * 3. Renders capability-specific copy for `asset_creation`.
 * 4. Falls back to generic copy when the capability is unknown / missing.
 * 5. Surfaces the capability key in a stable `data-testid` for
 *    support-ticket discoverability.
 * 6. Exposes a "Back to dashboard" link for the user's next action.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { DisabledCapabilityPage } from './DisabledCapabilityPage';

function renderAt(path: string, state?: { capability?: string }) {
  return render(
    <MemoryRouter
      initialEntries={[
        state ? { pathname: path, state } : path,
      ]}
    >
      <Routes>
        <Route path={path} element={<DisabledCapabilityPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DisabledCapabilityPage', () => {
  it('renders capability-specific copy for asset_creation when state.capability is set', () => {
    renderAt('/unavailable', { capability: 'asset_creation' });
    expect(
      screen.getByText(/Asset creation is currently disabled/i),
    ).toBeInTheDocument();
    // The capability key is exposed for support-ticket discoverability.
    expect(screen.getByTestId('capability-key')).toHaveTextContent(
      'asset_creation',
    );
  });

  it('falls back to generic copy when location.state is null', () => {
    renderAt('/unavailable');
    expect(
      screen.getByText(/This feature is currently unavailable/i),
    ).toBeInTheDocument();
    // No capability key rendered when there is no capability to surface.
    expect(screen.queryByTestId('capability-key')).toBeNull();
  });

  it('falls back to generic copy when capability is unknown', () => {
    renderAt('/unavailable', { capability: 'never_heard_of_this' });
    // Generic title (the fallback) — capability-specific copy doesn't fire.
    expect(
      screen.getByText(/This feature is currently unavailable/i),
    ).toBeInTheDocument();
    // But the capability key IS still surfaced (the fallback shows it).
    expect(screen.getByTestId('capability-key')).toHaveTextContent(
      'never_heard_of_this',
    );
  });

  it('honours an explicit capability prop over location.state', () => {
    render(
      <MemoryRouter
        initialEntries={[
          { pathname: '/x', state: { capability: 'overridden_by_state' } },
        ]}
      >
        <Routes>
          <Route
            path="/x"
            element={<DisabledCapabilityPage capability="asset_creation" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/Asset creation is currently disabled/i),
    ).toBeInTheDocument();
    // Prop wins over state.
    expect(screen.getByTestId('capability-key')).toHaveTextContent(
      'asset_creation',
    );
  });

  it('exposes the page via a data-testid + data-capability for E2E discoverability', () => {
    renderAt('/unavailable', { capability: 'asset_creation' });
    const page = screen.getByTestId('disabled-capability-page');
    expect(page.getAttribute('data-capability')).toBe('asset_creation');
  });

  it('renders a back-to-dashboard CTA so the user has a next action', () => {
    renderAt('/unavailable', { capability: 'asset_creation' });
    const link = screen.getByTestId('back-to-dashboard');
    expect(link).toHaveAttribute('href', '/');
  });
});
