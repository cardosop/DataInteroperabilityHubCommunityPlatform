/**
 * W5.4 (R2-F5) — dirty-state guard pins.
 *
 * Pre-fix no shared dirty-state guard existed at all: every wizard lost
 * unsaved work on navigation and on tab close with zero warning. The
 * guard must: block in-app navigation while dirty (confirm dialog with
 * proceed/stay), register beforeunload while dirty, and stay out of the
 * way when clean.
 *
 * Real router: createMemoryRouter (useBlocker is a data-router API) —
 * no router fakes.
 */

import { createMemoryRouter, Link, RouterProvider } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DirtyStateGuard } from './DirtyStateGuard';

function WizardProbe() {
  const [value, setValue] = useState('');
  const dirty = value !== '';
  return (
    <div>
      <input
        data-testid="wizard-input"
        aria-label="Contract name"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <Link to="/elsewhere" data-testid="leave-link">
        Go elsewhere
      </Link>
      <DirtyStateGuard dirty={dirty} />
    </div>
  );
}

function makeRouter() {
  return createMemoryRouter(
    [
      { path: '/wizard', element: <WizardProbe /> },
      { path: '/elsewhere', element: <div data-testid="elsewhere">Elsewhere page</div> },
    ],
    { initialEntries: ['/wizard'] },
  );
}

describe('DirtyStateGuard', () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let removeEventListenerSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('blocks navigation when dirty and proceeds on explicit discard', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter()} />);

    await user.type(screen.getByTestId('wizard-input'), 'draft');
    await user.click(screen.getByTestId('leave-link'));

    // Blocked: the confirm dialog is up, the target page has NOT rendered.
    expect(screen.getByText('Discard unsaved changes?')).toBeInTheDocument();
    expect(screen.queryByTestId('elsewhere')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /discard changes/i }));
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument();
  });

  it('stays on the page when the user keeps editing', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter()} />);

    await user.type(screen.getByTestId('wizard-input'), 'draft');
    await user.click(screen.getByTestId('leave-link'));
    expect(screen.getByText('Discard unsaved changes?')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /keep editing/i }));
    expect(screen.queryByTestId('elsewhere')).not.toBeInTheDocument();
    expect(screen.getByTestId('wizard-input')).toBeInTheDocument();
  });

  it('does not block navigation when clean (regression pin)', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter()} />);

    await user.click(screen.getByTestId('leave-link'));
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument();
    expect(screen.queryByText('Discard unsaved changes?')).not.toBeInTheDocument();
  });

  it('registers beforeunload only while dirty (tab-close guard)', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter()} />);

    // Clean: no beforeunload listener.
    expect(
      addEventListenerSpy.mock.calls.some(([name]) => name === 'beforeunload'),
    ).toBe(false);

    await user.type(screen.getByTestId('wizard-input'), 'draft');
    expect(
      addEventListenerSpy.mock.calls.some(([name]) => name === 'beforeunload'),
    ).toBe(true);

    // Back to clean: listener removed.
    await user.clear(screen.getByTestId('wizard-input'));
    expect(
      removeEventListenerSpy.mock.calls.some(([name]) => name === 'beforeunload'),
    ).toBe(true);
  });
});
