/**
 * Scheduled Export Create Page Tests
 * Verifies form renders with AssetMultiPicker, DatasetMultiPicker, FileMultiPicker, ContractPicker (task 29.69.6.1).
 * Real components; API client mocked for API calls.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ScheduledExportCreatePage } from './ScheduledExportCreatePage';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

describe('ScheduledExportCreatePage', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

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
    mockClient = realClient;
    vi.mocked(mockClient.get).mockResolvedValue({
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
