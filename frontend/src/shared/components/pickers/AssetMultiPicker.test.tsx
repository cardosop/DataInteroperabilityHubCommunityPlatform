/**
 * AssetMultiPicker Unit Tests
 * Per task 29.69.3.4. Multi-select, keyboard nav, error handling.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import { AssetMultiPicker } from './AssetMultiPicker';

describe('AssetMultiPicker', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  const mockAssets = {
    results: [
      { id: 'a1', name: 'Asset One', key: 'asset-one' },
      { id: 'a2', name: 'Asset Two', key: 'asset-two' },
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
      if (u.includes('assets') && !u.includes('assets/a1') && !u.includes('assets/a2')) {
        return Promise.resolve({ data: mockAssets });
      }
      if (u.includes('assets/a1')) {
        return Promise.resolve({ data: mockAssets.results[0] });
      }
      if (u.includes('assets/a2')) {
        return Promise.resolve({ data: mockAssets.results[1] });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
  });

  it('renders with placeholder', () => {
    render(<AssetMultiPicker value={[]} onChange={() => {}} />, { wrapper });
    expect(screen.getByPlaceholderText(/search and select assets/i)).toBeInTheDocument();
  });

  it('toggles selection on click', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AssetMultiPicker value={[]} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select assets/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Asset One')).toBeInTheDocument());
    await user.click(screen.getByText('Asset One'));
    expect(onChange).toHaveBeenCalledWith(['a1']);
  });

  it('adds to selection when multiple clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AssetMultiPicker value={['a1']} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select assets/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Asset Two')).toBeInTheDocument());
    await user.click(screen.getByText('Asset Two'));
    expect(onChange).toHaveBeenCalledWith(['a1', 'a2']);
  });

  it('removes from selection when selected item clicked again', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AssetMultiPicker value={['a1', 'a2']} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select assets/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Asset One')).toBeInTheDocument());
    await user.click(screen.getByText('Asset One'));
    expect(onChange).toHaveBeenCalledWith(['a2']);
  });

  it('shows error state when network fails', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<AssetMultiPicker value={[]} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select assets/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/failed to load assets/i)).toBeInTheDocument();
    });
  });

  it('has aria-multiselectable on listbox', async () => {
    const user = userEvent.setup();
    render(<AssetMultiPicker value={[]} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select assets/i });
    await user.click(input);
    await waitFor(() => {
      const listbox = screen.getByRole('listbox', { name: /asset options/i });
      expect(listbox).toHaveAttribute('aria-multiselectable', 'true');
    });
  });
});
