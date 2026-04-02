/**
 * OrderDetailPage tests — Phase 112.D.2
 *
 * Verifies:
 * 1. No window.prompt — rejection uses modal dialog
 * 2. Rejection dialog renders with textarea for reason
 * 3. Error boundary catches render errors
 */
import type { HttpClient } from '../../../shared/types/api';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { OrderDetailPage } from './OrderDetailPage';
import { ErrorBoundary } from '../../../shared/components/ErrorBoundary';

vi.mock('../../../shared/services/errorReporting', () => ({
  errorReportingService: { reportError: vi.fn() },
}));

const MOCK_ORDER = {
  id: 'order-uuid-123',
  listing: 'listing-uuid-456',
  listing_title: 'Test Listing',
  status: 'REQUESTED',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  approved_at: null,
  rejected_at: null,
  fulfilled_at: null,
  rejection_reason: null,
  asset_id: null,
};

describe('OrderDetailPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/marketplace/orders/order-uuid-123']}>
          <Routes>
            <Route path="/marketplace/orders/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockResolvedValue({ data: MOCK_ORDER });
  });

  it('renders without crashing', async () => {
    render(<OrderDetailPage />, { wrapper: Wrapper });
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('does not use window.prompt for rejection', async () => {
    const promptSpy = vi.spyOn(window, 'prompt');
    render(<OrderDetailPage />, { wrapper: Wrapper });

    // Wait for order data to load and reject button to appear
    const rejectBtn = await screen.findByText('Reject Order');
    fireEvent.click(rejectBtn);

    // window.prompt must NOT have been called
    expect(promptSpy).not.toHaveBeenCalled();
    promptSpy.mockRestore();
  });

  it('shows rejection dialog with textarea when Reject clicked', async () => {
    render(<OrderDetailPage />, { wrapper: Wrapper });

    const rejectBtn = await screen.findByText('Reject Order');
    fireEvent.click(rejectBtn);

    // Modal dialog must appear with the expected elements
    await waitFor(() => {
      expect(screen.getByText('Reject Order', { selector: 'h2' })).toBeTruthy();
    });
    expect(screen.getByLabelText(/reason for rejection/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/enter rejection reason/i)).toBeTruthy();
  });

  it('closes rejection dialog on Cancel', async () => {
    render(<OrderDetailPage />, { wrapper: Wrapper });

    const rejectBtn = await screen.findByText('Reject Order');
    fireEvent.click(rejectBtn);

    // Dialog opens
    await waitFor(() => {
      expect(screen.getByText('Reject Order', { selector: 'h2' })).toBeTruthy();
    });

    // Click the Cancel button inside the dialog
    const cancelBtns = screen.getAllByText('Cancel');
    const dialogCancelBtn = cancelBtns.find(
      (btn) => btn.closest('.confirm-dialog-actions'),
    );
    expect(dialogCancelBtn).toBeTruthy();
    fireEvent.click(dialogCancelBtn!);

    // Dialog should close — the h2 title should disappear
    await waitFor(() => {
      expect(screen.queryByText('Reject Order', { selector: 'h2' })).toBeNull();
    });
  });

  it('wraps in ErrorBoundary without crash', () => {
    const origError = console.error;
    console.error = vi.fn();
    try {
      function BrokenChild() {
        throw new Error('render crash');
      }
      const { container } = render(
        <ErrorBoundary>
          <BrokenChild />
        </ErrorBoundary>,
      );
      // ErrorBoundary should catch and show fallback
      expect(container.textContent).toContain('Something went wrong');
    } finally {
      console.error = origError;
    }
  });
});
