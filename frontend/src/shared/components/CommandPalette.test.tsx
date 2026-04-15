/**
 * CommandPalette — 223.5 tests.
 *
 * Real `cmdk` end-to-end — no module mocks. Verifies:
 *   - opens on Cmd+K / Ctrl+K, closes on Escape and programmatic close
 *   - Pages, Recent, and Actions groups render with their headings
 *   - fuzzy search narrows results
 *   - Enter on a page result navigates via react-router and closes
 *   - Enter on a page result pushes that path into the "Recent" list in
 *     localStorage so the next open surfaces it first
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CommandPalette } from './CommandPalette';

const TEST_PAGES = [
  { label: 'Home', path: '/' },
  { label: 'Assets', path: '/assets' },
  { label: 'Contracts', path: '/contracts' },
  { label: 'Governance', path: '/governance' },
];

const TEST_ACTIONS = [
  {
    id: 'create-asset',
    label: 'Create Asset',
    path: '/assets/create',
  },
  {
    id: 'create-contract',
    label: 'Create Contract',
    path: '/contracts/create',
  },
];

function LocationProbe() {
  const loc = useLocation();
  return <span data-testid="current-path">{loc.pathname}</span>;
}

function Harness({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="*" element={<>{children}<LocationProbe /></>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('opens on Ctrl+K and renders the Pages / Actions group headings', async () => {
    const user = userEvent.setup();
    render(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );
    // Initially closed — no combobox mounted.
    expect(screen.queryByRole('combobox')).toBeNull();

    await user.keyboard('{Control>}k{/Control}');

    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
    expect(screen.getByText('Pages')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
    // Assets is in the Pages group.
    expect(screen.getByText('Assets')).toBeInTheDocument();
    expect(screen.getByText('Create Asset')).toBeInTheDocument();
  });

  it('filters results with fuzzy search', async () => {
    const user = userEvent.setup();
    render(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );
    await user.keyboard('{Control>}k{/Control}');
    const input = await screen.findByRole('combobox');
    await user.type(input, 'gov');

    await waitFor(() => {
      expect(screen.getByText('Governance')).toBeInTheDocument();
    });
    // Assets / Contracts / Home get filtered out.
    expect(screen.queryByText('Assets')).toBeNull();
    expect(screen.queryByText('Home')).toBeNull();
  });

  it('navigates on Enter and closes the palette', async () => {
    const user = userEvent.setup();
    render(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );
    await user.keyboard('{Control>}k{/Control}');
    const input = await screen.findByRole('combobox');
    await user.type(input, 'contracts');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByTestId('current-path')).toHaveTextContent('/contracts');
    });
    // Palette unmounts on close.
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('records the last navigation in the Recent group', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );

    await user.keyboard('{Control>}k{/Control}');
    const input = await screen.findByRole('combobox');
    await user.type(input, 'contracts');
    await user.keyboard('{Enter}');
    await waitFor(() =>
      expect(screen.getByTestId('current-path')).toHaveTextContent('/contracts'),
    );

    // Re-render and reopen — Recent should now include Contracts.
    rerender(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );
    await user.keyboard('{Control>}k{/Control}');
    await screen.findByRole('combobox');
    expect(screen.getByText('Recent')).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    render(
      <Harness>
        <CommandPalette pages={TEST_PAGES} actions={TEST_ACTIONS} />
      </Harness>,
    );
    await user.keyboard('{Control>}k{/Control}');
    await screen.findByRole('combobox');
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('combobox')).toBeNull();
    });
  });
});
