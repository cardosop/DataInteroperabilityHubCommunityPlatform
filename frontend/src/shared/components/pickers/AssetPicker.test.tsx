/**
 * AssetPicker Unit Tests
 * Per task 29.68.6.1. Searchable single-select, keyboard nav, selection.
 * Uses axios mock for assets list; real AssetPicker component.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssetPicker } from './AssetPicker';

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

import { apiClient } from '../../api/client';

describe('AssetPicker', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

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
        <MemoryRouter>
          {children}
        </MemoryRouter>
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
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({ data: mockAssets });
  });

  it('renders with placeholder', () => {
    render(
      <AssetPicker value={null} onChange={() => {}} />,
      { wrapper }
    );

    expect(screen.getByPlaceholderText(/search and select an asset/i)).toBeInTheDocument();
  });

  it('fetches assets when dropdown opened', async () => {
    const user = userEvent.setup();
    render(
      <AssetPicker value={null} onChange={() => {}} />,
      { wrapper }
    );

    const input = screen.getByRole('combobox', { name: /select asset/i });
    await user.click(input);

    await waitFor(() => {
      expect(mockAxiosInstance.get).toHaveBeenCalled();
    });
  });

  it('displays asset options when loaded', async () => {
    const user = userEvent.setup();
    render(
      <AssetPicker value={null} onChange={() => {}} />,
      { wrapper }
    );

    const input = screen.getByRole('combobox', { name: /select asset/i });
    await user.click(input);

    await waitFor(() => {
      expect(screen.getByText('Asset One')).toBeInTheDocument();
      expect(screen.getByText('Asset Two')).toBeInTheDocument();
    });
  });

  it('calls onChange when asset selected', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <AssetPicker value={null} onChange={onChange} />,
      { wrapper }
    );

    const input = screen.getByRole('combobox', { name: /select asset/i });
    await user.click(input);

    await waitFor(() => {
      expect(screen.getByText('Asset One')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Asset One'));

    expect(onChange).toHaveBeenCalledWith('a1');
  });

  it('selects asset via keyboard (ArrowDown + Enter)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <AssetPicker value={null} onChange={onChange} />,
      { wrapper }
    );

    const input = screen.getByRole('combobox', { name: /select asset/i });
    await user.click(input);

    await waitFor(() => {
      expect(screen.getByText('Asset One')).toBeInTheDocument();
    });

    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith('a1');
  });

  it('handles invalid selection (deleted asset): clear button allows user to reset', async () => {
    vi.spyOn(mockAxiosInstance, 'get').mockImplementation((url: string) => {
      const u = url ?? '';
      if (u.includes('assets') && !u.includes('assets/invalid-id')) {
        return Promise.resolve({ data: mockAssets });
      }
      if (u.includes('assets/invalid-id')) {
        return Promise.reject({
          response: { status: 404, data: { detail: 'Not found.' } },
        });
      }
      return Promise.resolve({ data: mockAssets });
    });

    const onChange = vi.fn();
    render(<AssetPicker value="invalid-id" onChange={onChange} />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument();
    });

    await userEvent.setup().click(screen.getByRole('button', { name: /clear selection/i }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('shows clear button when value selected', async () => {
    vi.mocked(mockAxiosInstance.get).mockImplementation((url: string) => {
      if (url?.includes('/assets/') && url?.includes('/a1')) {
        return Promise.resolve({ data: { id: 'a1', name: 'Asset One', key: 'asset-one' } });
      }
      return Promise.resolve({ data: mockAssets });
    });

    render(
      <AssetPicker value="a1" onChange={() => {}} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument();
    });
  });
});
