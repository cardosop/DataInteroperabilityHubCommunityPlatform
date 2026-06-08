/**
 * Phase 277.B.028 — RoPA ListPage Vitest component tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RopaListPage } from '../RopaListPage';
import * as apiModule from '../../../../shared/api/client';

const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({
      get: mockGet,
      post: mockPost,
    }),
  },
}));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <RopaListPage />
    </QueryClientProvider>,
  );
}

describe('RopaListPage', () => {
  it('shows loading skeleton initially', () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByTestId('detail-page-skeleton')).toBeDefined();
  });

  it('shows error display on API failure', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('error-display')).toBeDefined();
    });
  });

  it('shows empty state when no generations exist', async () => {
    mockGet.mockResolvedValue({ data: { results: [] } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeDefined();
    });
  });

  it('renders generation table with rows', async () => {
    mockGet.mockResolvedValue({
      data: {
        results: [
          {
            id: '1',
            regulation: 'GDPR',
            output_format: 'pdf',
            status: 'COMPLETED',
            created_at: '2026-05-13T00:00:00Z',
          },
        ],
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-table')).toBeDefined();
      expect(screen.getByTestId('ropa-row-1')).toBeDefined();
    });
  });

  it('renders regulation select and generate button', async () => {
    mockGet.mockResolvedValue({ data: { results: [] } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-regulation-select')).toBeDefined();
      expect(screen.getByTestId('ropa-generate-btn')).toBeDefined();
    });
  });
});
