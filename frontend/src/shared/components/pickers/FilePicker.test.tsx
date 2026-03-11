/**
 * FilePicker Unit Tests
 * Per task 29.69.3.4. Searchable single-select, keyboard nav, error handling.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import { FilePicker } from './FilePicker';

describe('FilePicker', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  const mockFiles = {
    results: [
      { id: 'f1', name: 'file-one.csv', content_type: 'text/csv' },
      { id: 'f2', name: 'file-two.json', content_type: 'application/json' },
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
      if (u.includes('files') && !u.includes('files/f1') && !u.includes('files/f2')) {
        return Promise.resolve({ data: mockFiles });
      }
      if (u.includes('files/f1')) {
        return Promise.resolve({ data: mockFiles.results[0] });
      }
      if (u.includes('files/f2')) {
        return Promise.resolve({ data: mockFiles.results[1] });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
  });

  it('renders with placeholder', () => {
    render(<FilePicker value={null} onChange={() => {}} />, { wrapper });
    expect(screen.getByPlaceholderText(/search and select a file/i)).toBeInTheDocument();
  });

  it('fetches files when dropdown opened', async () => {
    const user = userEvent.setup();
    render(<FilePicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select file/i });
    await user.click(input);
    await waitFor(() => expect(mockAxiosInstance.get).toHaveBeenCalled());
  });

  it('displays file options when loaded', async () => {
    const user = userEvent.setup();
    render(<FilePicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select file/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('file-one.csv')).toBeInTheDocument();
      expect(screen.getByText('file-two.json')).toBeInTheDocument();
    });
  });

  it('calls onChange when file selected', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FilePicker value={null} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select file/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('file-one.csv')).toBeInTheDocument());
    await user.click(screen.getByText('file-one.csv'));
    expect(onChange).toHaveBeenCalledWith('f1');
  });

  it('shows error state when network fails', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<FilePicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select file/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/failed to load files/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no files found', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockResolvedValueOnce({
      data: { results: [], count: 0 },
    });
    const user = userEvent.setup();
    render(<FilePicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select file/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/no files found/i)).toBeInTheDocument();
    });
  });
});
