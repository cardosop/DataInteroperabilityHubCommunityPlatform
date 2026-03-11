/**
 * ContractPicker Unit Tests
 * Per task 29.69.3.4. Searchable single-select, keyboard nav, error handling.
 * Uses apiClient instance mock for contracts list; real ContractPicker component.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import { ContractPicker } from './ContractPicker';

describe('ContractPicker', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  const mockContracts = {
    results: [
      { id: 'c1', name: 'Contract One', original_spec_type: 'ODCS' },
      { id: 'c2', name: 'Contract Two', original_spec_type: 'ODPS' },
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
      if (u.includes('contracts') && !u.includes('contracts/c1') && !u.includes('contracts/c2')) {
        return Promise.resolve({ data: mockContracts });
      }
      if (u.includes('contracts/c1')) {
        return Promise.resolve({ data: mockContracts.results[0] });
      }
      if (u.includes('contracts/c2')) {
        return Promise.resolve({ data: mockContracts.results[1] });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });
  });

  it('renders with placeholder', () => {
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    expect(screen.getByPlaceholderText(/search and select a contract/i)).toBeInTheDocument();
  });

  it('fetches contracts when dropdown opened', async () => {
    const user = userEvent.setup();
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => {
      expect(mockAxiosInstance.get).toHaveBeenCalled();
    });
  });

  it('displays contract options when loaded', async () => {
    const user = userEvent.setup();
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('Contract One')).toBeInTheDocument();
      expect(screen.getByText('Contract Two')).toBeInTheDocument();
    });
  });

  it('calls onChange when contract selected', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ContractPicker value={null} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Contract One')).toBeInTheDocument());
    await user.click(screen.getByText('Contract One'));
    expect(onChange).toHaveBeenCalledWith('c1');
  });

  it('selects contract via keyboard (ArrowDown + Enter)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ContractPicker value={null} onChange={onChange} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => expect(screen.getByText('Contract One')).toBeInTheDocument());
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('c1');
  });

  it('shows error state when network fails', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/failed to load contracts/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no contracts found', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockResolvedValueOnce({
      data: { results: [], count: 0 },
    });
    const user = userEvent.setup();
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText(/no contracts found/i)).toBeInTheDocument();
    });
  });

  it('has correct ARIA attributes', async () => {
    const user = userEvent.setup();
    render(<ContractPicker value={null} onChange={() => {}} />, { wrapper });
    const input = screen.getByRole('combobox', { name: /select contract/i });
    expect(input).toHaveAttribute('aria-expanded', 'false');
    expect(input).toHaveAttribute('aria-haspopup', 'listbox');
    await user.click(input);
    await waitFor(() => expect(input).toHaveAttribute('aria-expanded', 'true'));
  });
});
