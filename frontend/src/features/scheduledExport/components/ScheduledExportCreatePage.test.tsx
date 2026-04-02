/**
 * Scheduled Export Create Page Tests
 * Verifies form renders with AssetMultiPicker, DatasetMultiPicker, FileMultiPicker, ContractPicker (task 29.69.6.1).
 * Real components; axios mocked for API calls.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ScheduledExportCreatePage } from './ScheduledExportCreatePage';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
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

describe('ScheduledExportCreatePage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: { results: [], count: 0 },
    } as never);
  });

  it('should render form with multi-pickers and ContractPicker', () => {
    render(<ScheduledExportCreatePage />, { wrapper });

    expect(screen.getByTestId('scheduled-export-create-page')).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByTestId('scheduled-export-asset-picker')).toBeInTheDocument();
    expect(screen.getByTestId('scheduled-export-dataset-picker')).toBeInTheDocument();
    expect(screen.getByTestId('scheduled-export-file-picker')).toBeInTheDocument();
    expect(screen.getByTestId('scheduled-export-contract-picker')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument();
  });
});
