/**
 * DatasetMultiPicker Unit Tests
 * Per task 29.69.3.4. Multi-select, error handling.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import { DatasetMultiPicker } from './DatasetMultiPicker';

describe('DatasetMultiPicker', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  const mockDatasets = {
    results: [
      { id: 'd1', name: 'Dataset One', format: 'CSV' },
      { id: 'd2', name: 'Dataset Two', format: 'JSON' },
    ],
    count: 2,
  };

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    mockAxiosInstance = apiClient.getClient();
    vi.spyOn(mockAxiosInstance, 'get').mockImplementation((url: string) => {
      const u = url ?? '';
      if (u.includes('datasets') && !u.includes('datasets/d1') && !u.includes('datasets/d2')) {
        return Promise.resolve({ data: mockDatasets });
      }
      if (u.includes('datasets/d1')) {
        return Promise.resolve({ data: mockDatasets.results[0] });
      }
      if (u.includes('datasets/d2')) {
        return Promise.resolve({ data: mockDatasets.results[1] });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
  });

  it('renders with placeholder', () => {
    render(<DatasetMultiPicker value={[]} onChange={() => {}} />, { wrapper });
    expect(screen.getByPlaceholderText(/search and select datasets/i)).toBeInTheDocument();
  });

  it('toggles selection on click', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DatasetMultiPicker value={[]} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select datasets/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Dataset One')).toBeInTheDocument());
    await user.click(screen.getByText('Dataset One'));
    expect(onChange).toHaveBeenCalledWith(['d1']);
  });

  it('shows error state when network fails', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<DatasetMultiPicker value={[]} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select datasets/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/failed to load datasets/i)).toBeInTheDocument();
    });
  });
});
