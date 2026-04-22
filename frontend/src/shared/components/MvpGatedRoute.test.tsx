/**
 * Track A PR 4 — unit tests for <MvpGatedRoute>.
 *
 * The component reads `isMvpModeEnabledFromEnv()` (which inspects
 * `import.meta.env.VITE_MVP_MODE`). Build-inlined env vars don't survive
 * Vitest's `vi.stubEnv` cleanly across modules, so we mock the helper
 * directly — narrower scope, less coupling to Vite internals.
 *
 * Behaviors covered:
 *   1. MVP off + non-MVP path  → renders children (gate inactive)
 *   2. MVP on  + MVP-safe path → renders children
 *   3. MVP on  + path in NON_MVP_PATHS → redirects to /coming-soon
 *   4. MVP on  + child of a NON_MVP_PATHS prefix (e.g. /mesh/topology
 *      when /mesh is gated) → redirects (hierarchical match)
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../features/shell/utils/mvpNav', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../features/shell/utils/mvpNav')>();
  return {
    ...actual,
    isMvpModeEnabledFromEnv: vi.fn(),
  };
});

import { isMvpModeEnabledFromEnv } from '../../features/shell/utils/mvpNav';
import { MvpGatedRoute } from './MvpGatedRoute';

const mockedIsMvpModeEnabled = vi.mocked(isMvpModeEnabledFromEnv);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/coming-soon"
          element={<div data-testid="coming-soon">coming soon</div>}
        />
        <Route
          path="*"
          element={
            <MvpGatedRoute>
              <div data-testid="children">protected content</div>
            </MvpGatedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('<MvpGatedRoute>', () => {
  beforeEach(() => {
    mockedIsMvpModeEnabled.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders children when MVP mode is off, regardless of path', () => {
    mockedIsMvpModeEnabled.mockReturnValue(false);
    renderAt('/mesh');
    expect(screen.getByTestId('children')).toBeInTheDocument();
    expect(screen.queryByTestId('coming-soon')).not.toBeInTheDocument();
  });

  it('renders children when MVP mode is on but the path is MVP-safe', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    renderAt('/assets');
    expect(screen.getByTestId('children')).toBeInTheDocument();
  });

  it('redirects to /coming-soon when MVP mode is on and path is in NON_MVP_PATHS', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    renderAt('/mesh');
    expect(screen.getByTestId('coming-soon')).toBeInTheDocument();
    expect(screen.queryByTestId('children')).not.toBeInTheDocument();
  });

  it('redirects on hierarchical match: /mesh/topology when /mesh is gated', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    renderAt('/mesh/topology');
    expect(screen.getByTestId('coming-soon')).toBeInTheDocument();
  });

  it('redirects on /ai/* prefix match (MVP_PREFIX_PATHS)', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    renderAt('/ai/search');
    expect(screen.getByTestId('coming-soon')).toBeInTheDocument();
  });

  it('redirects each newly-gated path added in PR 3', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    for (const p of ['/search', '/developer', '/observability']) {
      const { unmount } = renderAt(p);
      expect(
        screen.getByTestId('coming-soon'),
        `${p} should redirect to /coming-soon under MVP mode`,
      ).toBeInTheDocument();
      unmount();
    }
  });

  it('does NOT redirect /semantic (MVP-scope, never gated)', () => {
    mockedIsMvpModeEnabled.mockReturnValue(true);
    renderAt('/semantic');
    expect(screen.getByTestId('children')).toBeInTheDocument();
    expect(screen.queryByTestId('coming-soon')).not.toBeInTheDocument();
  });
});
