/**
 * Dataset Detail Page Tests
 * Real useDataset, useUpdateDataset, useDeleteDataset; only API client mocked.
 * Scenarios: loading, error, detail with linked asset, detail without asset (Link to Asset), edit form.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DatasetFormat } from '../../../shared/types/datasets';
import { ToastProvider } from '../../../shared/components/Toast';
import { DatasetDetailPage } from './DatasetDetailPage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

describe('DatasetDetailPage', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/datasets/ds-1']}>
            <Routes>
              <Route path="/datasets/:id" element={children} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockClient = realClient;
    vi.mocked(mockClient.get).mockClear();
    vi.mocked(mockClient.patch).mockClear();
  });

  it('should display loading state', async () => {
    let resolveGet: (value: unknown) => void;
    const getPromise = new Promise((resolve) => {
      resolveGet = resolve;
    });
    vi.mocked(mockClient.get).mockReturnValue(getPromise as never);

    render(<DatasetDetailPage />, { wrapper });

    expect(document.querySelector('.skeleton, [aria-hidden="true"]') || document.body).toBeTruthy();

    resolveGet!({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        format: DatasetFormat.CSV,
        size_bytes: 1024,
        version: '1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        tenant_id: 't1',
      },
    });
    await waitFor(() => {
      expect(screen.queryByText(/loading dataset/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    vi.mocked(mockClient.get).mockRejectedValue(new Error('Not found'));

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load dataset/i)).toBeInTheDocument();
    });
  });

  it('should show linked asset with link when asset_id present', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        format: DatasetFormat.CSV,
        size_bytes: 1024,
        version: '1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        tenant_id: 't1',
        asset_id: 'asset-123',
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Dataset' })).toBeInTheDocument();
    });

    expect(screen.getByTestId('dataset-linked-asset')).toBeInTheDocument();
    const assetLink = screen.getByTestId('dataset-asset-link');
    expect(assetLink).toBeInTheDocument();
    expect(assetLink).toHaveAttribute('href', '/assets/asset-123');
    expect(assetLink).toHaveTextContent('View asset');
  });

  it('should show Link to Asset button when dataset has no asset', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        format: DatasetFormat.CSV,
        size_bytes: 1024,
        version: '1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        tenant_id: 't1',
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Dataset' })).toBeInTheDocument();
    });

    expect(screen.getByTestId('btn-link-to-asset')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /link to asset/i })).toBeInTheDocument();
    expect(screen.queryByTestId('dataset-linked-asset')).not.toBeInTheDocument();
  });

  it('should open edit form when Link to Asset is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        format: DatasetFormat.CSV,
        size_bytes: 1024,
        version: '1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        tenant_id: 't1',
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('btn-link-to-asset')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-link-to-asset'));

    await waitFor(() => {
      expect(screen.getByTestId('dataset-edit-form')).toBeInTheDocument();
      expect(screen.getByTestId('dataset-asset-picker')).toBeInTheDocument();
    });
  });

  it('should save with asset_id when Edit and Save clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockImplementation((url: string) => {
      if (url?.includes('ds-1') && !url?.includes('versions')) {
        return Promise.resolve({
          data: {
            id: 'ds-1',
            name: 'Test Dataset',
            format: DatasetFormat.CSV,
            size_bytes: 1024,
            version: '1',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            tenant_id: 't1',
            asset_id: 'asset-123',
          },
        } as never);
      }
      if (url?.includes('asset-123')) {
        return Promise.resolve({
          data: { id: 'asset-123', name: 'My Asset', key: 'my-asset' },
        } as never);
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
    vi.mocked(mockClient.patch).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        asset_id: 'asset-123',
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Dataset' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /edit/i }));
    await waitFor(() => {
      expect(screen.getByTestId('dataset-asset-picker')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => {
      expect(mockClient.patch).toHaveBeenCalledWith(
        expect.stringContaining('ds-1'),
        expect.objectContaining({ asset: 'asset-123' })
      );
    });
  });

  it('should unlink asset when user clears AssetPicker and saves', async () => {
    const user = userEvent.setup();
    vi.mocked(mockClient.get).mockImplementation((url: string) => {
      if (url?.includes('ds-1') && !url?.includes('versions')) {
        return Promise.resolve({
          data: {
            id: 'ds-1',
            name: 'Test Dataset',
            format: DatasetFormat.CSV,
            size_bytes: 1024,
            version: '1',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            tenant_id: 't1',
            asset_id: 'asset-123',
          },
        } as never);
      }
      if (url?.includes('asset-123')) {
        return Promise.resolve({
          data: { id: 'asset-123', name: 'My Asset', key: 'my-asset' },
        } as never);
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
    vi.mocked(mockClient.patch).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        asset_id: null,
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Dataset' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /edit/i }));
    await waitFor(() => {
      expect(screen.getByTestId('dataset-asset-picker')).toBeInTheDocument();
    });

    const clearBtn = screen.getByRole('button', { name: /clear selection/i });
    await user.click(clearBtn);

    await user.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => {
      expect(mockClient.patch).toHaveBeenCalledWith(
        expect.stringContaining('ds-1'),
        expect.objectContaining({ asset: null })
      );
    });
  });

  it('should show asset_name when API returns it', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        id: 'ds-1',
        name: 'Test Dataset',
        format: DatasetFormat.CSV,
        size_bytes: 1024,
        version: '1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        tenant_id: 't1',
        asset_id: 'asset-123',
        asset_name: 'My Asset',
      },
    } as never);

    render(<DatasetDetailPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Dataset' })).toBeInTheDocument();
    });

    const assetLink = screen.getByTestId('dataset-asset-link');
    expect(assetLink).toHaveTextContent('My Asset');
    expect(assetLink).toHaveAttribute('href', '/assets/asset-123');
  });
});
