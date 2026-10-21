/**
 * Phase 277.B.028 — RoPA ListPage Vitest component tests.
 * 276.B.104 — lifecycle coverage: note edit (PATCH) + retire (DELETE).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RopaListPage } from '../RopaListPage';

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPatch = vi.fn();
const mockDelete = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({
      get: mockGet,
      post: mockPost,
      patch: mockPatch,
      delete: mockDelete,
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

const completedRow = {
  id: 'gen-1',
  regulation: 'GDPR',
  output_format: 'pdf',
  status: 'COMPLETED',
  created_at: '2026-05-13T00:00:00Z',
  summary_json: {},
  gaps_json: [],
};

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
      data: { results: [completedRow] },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-table')).toBeDefined();
      expect(screen.getByTestId('ropa-row-gen-1')).toBeDefined();
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

  it('renders note and retire actions per row (276.B.104)', async () => {
    mockGet.mockResolvedValue({ data: { results: [completedRow] } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-note-btn-gen-1')).toBeDefined();
      expect(screen.getByTestId('ropa-delete-btn-gen-1')).toBeDefined();
      expect(screen.getByTestId('ropa-note-text-gen-1')).toBeDefined();
    });
  });

  it('saves a note via PATCH and renders it after refetch (276.B.104 edit step)', async () => {
    const withNote = {
      ...completedRow,
      summary_json: { notes: 'Reviewed with legal' },
    };
    mockGet
      .mockResolvedValueOnce({ data: { results: [completedRow] } })
      .mockResolvedValue({ data: { results: [withNote] } });
    mockPatch.mockResolvedValue({ data: withNote });

    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-note-btn-gen-1')).toBeDefined();
    });

    fireEvent.click(screen.getByTestId('ropa-note-btn-gen-1'));
    const input = screen.getByTestId('ropa-note-input-gen-1');
    fireEvent.change(input, { target: { value: 'Reviewed with legal' } });
    fireEvent.click(screen.getByTestId('ropa-note-save-gen-1'));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith(
        expect.stringContaining('ropa/generations/gen-1/update/'),
        { summary_json: { notes: 'Reviewed with legal' } },
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('ropa-note-text-gen-1').textContent).toBe(
        'Reviewed with legal',
      );
    });
  });

  it('retires a record via DELETE after confirm (276.B.104 retire step)', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { results: [completedRow] } })
      .mockResolvedValue({ data: { results: [] } });
    mockDelete.mockResolvedValue({});

    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('ropa-delete-btn-gen-1')).toBeDefined();
    });

    fireEvent.click(screen.getByTestId('ropa-delete-btn-gen-1'));
    fireEvent.click(screen.getByTestId('ropa-delete-confirm-gen-1'));

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith(
        expect.stringContaining('ropa/generations/gen-1/delete/'),
      );
    });
    await waitFor(() => {
      expect(screen.queryByTestId('ropa-row-gen-1')).toBeNull();
    });
  });
});
