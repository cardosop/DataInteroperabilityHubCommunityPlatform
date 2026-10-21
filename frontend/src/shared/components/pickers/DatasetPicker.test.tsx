/**
 * DatasetPicker Unit Tests
 * Per task 29.69.3.4. Searchable single-select, keyboard nav, error handling.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HttpClient } from '../../types/api';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import { DatasetPicker } from './DatasetPicker';

describe('DatasetPicker', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

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
    mockClient = apiClient.getClient();
    vi.spyOn(mockClient, 'get').mockImplementation((url: string) => {
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
    render(<DatasetPicker value={null} onChange={() => {}} />, { wrapper });
    expect(screen.getByPlaceholderText(/search and select a dataset/i)).toBeInTheDocument();
  });

  it('fetches datasets when dropdown opened', async () => {
    const user = userEvent.setup();
    render(<DatasetPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select dataset/i });
    await user.click(input);
    await waitFor(() => expect(mockClient.get).toHaveBeenCalled());
  });

  it('displays dataset options when loaded', async () => {
    const user = userEvent.setup();
    render(<DatasetPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select dataset/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('Dataset One')).toBeInTheDocument();
      expect(screen.getByText('Dataset Two')).toBeInTheDocument();
    });
  });

  it('calls onChange when dataset selected', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DatasetPicker value={null} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select dataset/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Dataset One')).toBeInTheDocument());
    await user.click(screen.getByText('Dataset One'));
    expect(onChange).toHaveBeenCalledWith('d1');
  });

  it('shows error state when network fails', async () => {
    vi.spyOn(mockClient, 'get').mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<DatasetPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select dataset/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/failed to load datasets/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no datasets found', async () => {
    vi.spyOn(mockClient, 'get').mockResolvedValueOnce({
      data: { results: [], count: 0 },
    });
    const user = userEvent.setup();
    render(<DatasetPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select dataset/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/no datasets found/i)).toBeInTheDocument();
    });
  });
});
