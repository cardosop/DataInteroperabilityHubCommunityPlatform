/**
 * File List Page Tests
 * Real useFiles and useDeleteFile; only axios mocked.
 * Scenarios: loading, error, empty list with upload button, table with upload button, upload modal.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { File as FileType } from '../../../shared/types/files';
import { ToastProvider } from '../../../shared/components/Toast';
import { FileListPage } from './FileListPage';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

import { apiClient } from '../../../shared/api/client';

describe('FileListPage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>{children}</MemoryRouter>
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
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
  });

  it('should display loading state', async () => {
    let resolveList: (value: unknown) => void;
    const listPromise = new Promise((resolve) => {
      resolveList = resolve;
    });
    vi.mocked(mockAxiosInstance.get).mockReturnValue(listPromise as any);

    render(<FileListPage />, { wrapper });

    expect(screen.getByText(/loading files/i)).toBeInTheDocument();

    resolveList!({
      data: {
        results: [],
        total_pages: 0,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    });
    await waitFor(() => {
      expect(screen.queryByText(/loading files/i)).not.toBeInTheDocument();
    });
  });

  it('should display error state', async () => {
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(new Error('Network error'));

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/failed to load files/i)).toBeInTheDocument();
    });
  });

  it('should display Upload File button in header when empty', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: [],
        total_pages: 0,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-list-page')).toBeInTheDocument();
    });

    const uploadBtn = screen.getByTestId('btn-upload-file');
    expect(uploadBtn).toBeInTheDocument();
    expect(uploadBtn).toHaveTextContent(/upload file/i);
  });

  it('should open upload modal when Upload File button is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: [],
        total_pages: 0,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('btn-upload-file')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-upload-file'));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /upload file/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/drag and drop a file here/i)).toBeInTheDocument();
  });

  it('should display Upload File button and table when files exist', async () => {
    const mockFiles: FileType[] = [
      {
        id: 'file-1',
        name: 'test.csv',
        content_type: 'text/csv',
        size: 1024,
        storage_path: '/path/to/file',
        status: 'COMPLETED',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        created_by: 'user-1',
        tenant_id: 'tenant-1',
      },
    ];

    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: mockFiles,
        total_pages: 1,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('test.csv')).toBeInTheDocument();
    });

    expect(screen.getByTestId('btn-upload-file')).toBeInTheDocument();
    expect(screen.getByTestId('file-list-table')).toBeInTheDocument();
  });

  it('should open delete ConfirmDialog when Delete is clicked', async () => {
    const user = userEvent.setup();
    const mockFiles: FileType[] = [
      {
        id: 'file-1',
        name: 'test.csv',
        content_type: 'text/csv',
        size: 1024,
        storage_path: '/path/to/file',
        status: 'COMPLETED',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        created_by: 'user-1',
        tenant_id: 'tenant-1',
      },
    ];

    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: mockFiles,
        total_pages: 1,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);
    vi.mocked(mockAxiosInstance.delete).mockResolvedValue({ data: null } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('test.csv')).toBeInTheDocument();
    });

    const deleteBtns = screen.getAllByRole('button', { name: /delete/i });
    const rowDeleteBtn = deleteBtns.find((b) => b.textContent === 'Delete');
    expect(rowDeleteBtn).toBeInTheDocument();
    await user.click(rowDeleteBtn!);

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /delete file/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/are you sure you want to delete "test\.csv"/i)).toBeInTheDocument();
  });

  it('should show Upload File action in empty state when no filters', async () => {
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: [],
        total_pages: 0,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-list-empty-state')).toBeInTheDocument();
    });

    const uploadBtns = screen.getAllByRole('button', { name: /upload file/i });
    expect(uploadBtns.length).toBeGreaterThanOrEqual(1);
    expect(uploadBtns.some((b) => b.className.includes('file-list-upload-btn'))).toBe(true);
    expect(screen.getByTestId('file-list-empty-state').querySelector('.empty-state-action')).toBeInTheDocument();
  });

  it('should show Clear filters action in empty state when filters applied', async () => {
    const user = userEvent.setup();
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: {
        results: [],
        total_pages: 0,
        page: 1,
        has_next: false,
        has_previous: false,
      },
    } as any);

    render(<FileListPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('file-list-empty-state')).toBeInTheDocument();
    });

    const assetFilter = screen.getByPlaceholderText(/asset id/i);
    await user.type(assetFilter, '550e8400-e29b-41d4-a716-446655440000');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear filters/i })).toBeInTheDocument();
    });
    expect(screen.getByTestId('file-list-empty-state').querySelector('.empty-state-action')).toHaveTextContent(
      /clear filters/i
    );
  });
});
