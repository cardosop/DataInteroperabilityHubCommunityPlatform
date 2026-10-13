/**
 * DelegationSettingsPage Tests — the settings-page contract
 * (close-test-coverage-gaps 4.5).
 *
 * Only the API client is mocked (the sanctioned component-test seam —
 * no mocks of application code). The pins lock:
 *  - the page reads the paginated list shape (``results``) and renders
 *    rows/empty state (the E2E selectors' contract),
 *  - create POSTs the FULL datetime payload (the date inputs carry
 *    yyyy-mm-dd; the API contract is ISO datetimes — whole-day windows:
 *    T00:00:00 start / T23:59:59 end),
 *  - the backend's classified 400 ``{"detail": ...}`` rides into the
 *    form error (never a bare "HTTP 400").
 * A regression back to raw cookie fetch (401) or date-only payloads
 * fails here.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

import { DelegationSettingsPage } from './DelegationSettingsPage';

function makeRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'del-1',
    delegate_email: 'cpo@example.com',
    delegate_name: 'CPO User',
    start_at: '2026-09-28T00:00:00Z',
    end_at: '2026-10-05T23:59:59Z',
    reason: 'Out of office',
    is_active: true,
    created_at: '2026-09-28T09:00:00Z',
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DelegationSettingsPage />
    </MemoryRouter>,
  );
}

describe('DelegationSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the loaded list from the paginated shape (root testid + row + Active badge)', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { count: 1, next: null, previous: null, results: [makeRecord()] },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('delegation-settings-page')).toBeInTheDocument();
    });
    expect(screen.getByTestId('delegation-row-del-1')).toBeInTheDocument();
    expect(screen.getByText('cpo@example.com')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders the honest empty state when the list has no rows', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { count: 0, next: null, previous: null, results: [] },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No active delegations.')).toBeInTheDocument();
    });
  });

  it('POSTs the full datetime payload and shows the success banner', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { count: 0, next: null, previous: null, results: [] },
    });
    const post = vi.mocked(apiClient.getClient().post).mockResolvedValueOnce({
      data: makeRecord(),
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No active delegations.')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('toggle-delegation-form'));
    fireEvent.change(screen.getByLabelText('Delegate Email'), {
      target: { value: 'cpo@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Start Date'), {
      target: { value: '2026-09-28' },
    });
    fireEvent.change(screen.getByLabelText('End Date'), {
      target: { value: '2026-10-05' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Delegation' }));

    await waitFor(() => {
      expect(screen.getByText('Delegation created successfully.')).toBeInTheDocument();
    });
    expect(post).toHaveBeenCalledWith('/governance/delegations/', {
      delegate_email: 'cpo@example.com',
      start_at: '2026-09-28T00:00:00',
      end_at: '2026-10-05T23:59:59',
      reason: undefined,
    });
  });

  it('surfaces the backend detail message in the form error', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { count: 0, next: null, previous: null, results: [] },
    });
    // The apiClient's REAL rejection shape — the normalized ApiError
    // envelope the client throws (NOT a raw axios rejection).
    vi.mocked(apiClient.getClient().post).mockRejectedValueOnce({
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Delegate email does not match an active user in this tenant.',
        http_status: 400,
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No active delegations.')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('toggle-delegation-form'));
    fireEvent.change(screen.getByLabelText('Delegate Email'), {
      target: { value: 'ghost@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Start Date'), {
      target: { value: '2026-09-28' },
    });
    fireEvent.change(screen.getByLabelText('End Date'), {
      target: { value: '2026-10-05' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Delegation' }));

    await waitFor(() => {
      expect(
        screen.getByText('Delegate email does not match an active user in this tenant.')
      ).toBeInTheDocument();
    });
  });
});
