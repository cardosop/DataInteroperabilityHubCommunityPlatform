/**
 * W5.4 (R2-F5) — DPIA wizard dirty-state adoption pins.
 *
 * Pre-fix the wizard had no dirty-state guard: edits typed since the
 * last Next were silently lost on navigation. Pins: a mid-draft
 * navigation is blocked (discard/stay dialog), a Next persist clears
 * dirty, and a submit clears dirty BEFORE its own redirect (the
 * persist-then-navigate race — the guard must not block the post-save
 * navigation).
 */

import { createMemoryRouter, Link, RouterProvider } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    capabilities: {},
    isLoading: false,
    isCapabilityAvailable: (key: string) => key === 'compliance_dpia',
    getCapability: () => undefined,
  }),
}));
vi.mock('../services/dpiaService', () => ({
  dpiaService: {
    get: vi.fn(),
    create: vi.fn(),
    patch: vi.fn(),
    submit: vi.fn(),
  },
}));

import { dpiaService } from '../services/dpiaService';
import { DpiaWizardPage } from './DpiaWizardPage';

const LEAVE_LINK = (
  <Link to="/elsewhere" data-testid="leave-link">
    Leave wizard
  </Link>
);

function makeRouter(routePath: string) {
  return createMemoryRouter(
    [
      {
        path: routePath,
        element: (
          <div>
            <DpiaWizardPage />
            {LEAVE_LINK}
          </div>
        ),
      },
      { path: '/elsewhere', element: <div data-testid="elsewhere">Elsewhere</div> },
    ],
    { initialEntries: [routePath] },
  );
}

describe('DpiaWizardPage dirty-state guard (W5.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dpiaService.create).mockImplementation(async (input) => ({
      id: 'draft-1',
      ...input,
    } as never));
    vi.mocked(dpiaService.patch).mockImplementation(async (id, input) => ({
      id,
      ...(input as object),
    } as never));
    vi.mocked(dpiaService.submit).mockResolvedValue({} as never);
  });

  it('blocks navigation away from a mid-draft edit', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter('/dpia/new')} />);

    await user.type(screen.getByLabelText('Title'), 'Draft DPIA');
    await user.click(screen.getByTestId('leave-link'));

    expect(screen.getByText('Discard unsaved changes?')).toBeInTheDocument();
    expect(screen.queryByTestId('elsewhere')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /discard changes/i }));
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument();
  });

  it('clears dirty after a Next persist (server-saved work is not unsaved)', async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={makeRouter('/dpia/new')} />);

    await user.type(screen.getByLabelText('Title'), 'Draft DPIA');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    // The draft was persisted server-side — navigating away must NOT block.
    await user.click(screen.getByTestId('leave-link'));
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument();
    expect(screen.queryByText('Discard unsaved changes?')).not.toBeInTheDocument();
  });

  it('does not block its own post-submit redirect (persist-then-navigate race)', async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(
      [
        {
          path: '/dpia/:dpiaId',
          element: (
            <div>
              <DpiaWizardPage />
              {LEAVE_LINK}
            </div>
          ),
        },
        {
          path: '/governance/dpia/review-queue',
          element: <div data-testid="review-queue">Review queue</div>,
        },
        { path: '/elsewhere', element: <div data-testid="elsewhere">Elsewhere</div> },
      ],
      { initialEntries: ['/dpia/draft-1'] },
    );
    vi.mocked(dpiaService.get).mockResolvedValue({
      id: 'draft-1',
      title: 'Existing',
      regime: 'GDPR',
      asset: null,
      wizard_payload: {},
    } as never);

    render(<RouterProvider router={router} />);

    await screen.findByDisplayValue('Existing');
    await user.type(screen.getByLabelText('Title'), ' (edited)');
    // Jump straight to the final step so Submit is reachable.
    for (let i = 0; i < 3; i++) {
      await user.click(screen.getByRole('button', { name: 'Next' }));
    }
    await user.click(screen.getByRole('button', { name: /submit for review/i }));

    expect(await screen.findByTestId('review-queue')).toBeInTheDocument();
    expect(screen.queryByText('Discard unsaved changes?')).not.toBeInTheDocument();
  });
});
