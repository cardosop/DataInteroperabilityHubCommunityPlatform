/**
 * SearchPage — 223.6 integration tests.
 *
 * Real SearchPage + real recentSearches util + real useDebouncedValue;
 * only `searchService.search` is spied so we can inspect the network
 * payload without hitting a backend.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { searchService } from '../services/searchService';
import { SearchPage } from './SearchPage';
import { RECENT_SEARCH_STORAGE_KEY } from '../../../shared/utils/recentSearches';

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

function successResponse(query: string, total: number, type: 'ASSET' | 'CONTRACT' = 'ASSET') {
  return {
    query,
    total,
    results: Array.from({ length: total }).map((_, i) => ({
      type,
      id: `${type.toLowerCase()}-${i}`,
      title: `${type} ${i}`,
      description: 'hit',
      relevance_score: 0.9,
    })),
  };
}

describe('SearchPage — 223.6', () => {
  let spy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    spy = vi.spyOn(searchService, 'search');
  });

  afterEach(() => {
    spy.mockRestore();
    localStorage.clear();
  });

  it('renders the scope tabs', () => {
    render(<SearchPage />, { wrapper: Wrapper });
    expect(screen.getByTestId('search-scope-ALL')).toBeInTheDocument();
    expect(screen.getByTestId('search-scope-ASSET')).toBeInTheDocument();
    expect(screen.getByTestId('search-scope-CONTRACT')).toBeInTheDocument();
    expect(screen.getByTestId('search-scope-DATASET')).toBeInTheDocument();
    expect(screen.getByTestId('search-scope-JOB')).toBeInTheDocument();
    expect(screen.getByTestId('search-scope-ORDER')).toBeInTheDocument();
  });

  it('auto-searches after the debounce window when the query changes', async () => {
    spy.mockResolvedValue(successResponse('alpha', 1));
    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    const input = screen.getByTestId('search-input');
    await user.type(input, 'alpha');
    await waitFor(
      () => {
        expect(spy).toHaveBeenCalled();
      },
      { timeout: 1500 },
    );
    expect(spy.mock.calls[spy.mock.calls.length - 1][0]).toBe('alpha');
  });

  it('does not fire a request for an empty query', async () => {
    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    const input = screen.getByTestId('search-input');
    await user.type(input, '   ');
    // Wait longer than the debounce window; still no call.
    await new Promise((r) => setTimeout(r, 400));
    expect(spy).not.toHaveBeenCalled();
  });

  it('switching scope triggers a new search with the type filter', async () => {
    spy.mockResolvedValue(successResponse('alpha', 1, 'CONTRACT'));
    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    await user.type(screen.getByTestId('search-input'), 'alpha');
    await waitFor(() => expect(spy).toHaveBeenCalled(), { timeout: 1500 });
    spy.mockClear();
    await user.click(screen.getByTestId('search-scope-CONTRACT'));
    await waitFor(
      () => {
        expect(spy).toHaveBeenCalled();
      },
      { timeout: 1500 },
    );
    const lastCall = spy.mock.calls[spy.mock.calls.length - 1];
    expect((lastCall[1] as { type?: string }).type).toBe('CONTRACT');
  });

  it('JOB and ORDER scopes skip the backend and show a "coming soon" empty state', async () => {
    spy.mockResolvedValue(successResponse('alpha', 1));
    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    await user.type(screen.getByTestId('search-input'), 'alpha');
    await waitFor(() => expect(spy).toHaveBeenCalled(), { timeout: 1500 });
    spy.mockClear();
    await user.click(screen.getByTestId('search-scope-JOB'));
    // Wait past the debounce window.
    await new Promise((r) => setTimeout(r, 400));
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/jobs search coming soon/i)).toBeInTheDocument();
  });

  it('records the query in localStorage and renders the recent dropdown on refocus', async () => {
    spy.mockResolvedValue(successResponse('alpha', 1));
    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    const input = screen.getByTestId('search-input');
    await user.type(input, 'alpha');
    await waitFor(() => expect(spy).toHaveBeenCalled(), { timeout: 1500 });

    // Confirm persisted.
    const raw = localStorage.getItem(RECENT_SEARCH_STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed[0].query).toBe('alpha');

    // Clear the input and refocus — recent dropdown should surface the entry.
    await user.clear(input);
    await user.click(input);
    expect(await screen.findByTestId('search-recent-dropdown')).toBeInTheDocument();
    expect(screen.getByTestId('search-recent-alpha')).toBeInTheDocument();
  });

  it('clicking a recent entry populates the input and triggers a re-search', async () => {
    // Seed storage with a past search.
    localStorage.setItem(
      RECENT_SEARCH_STORAGE_KEY,
      JSON.stringify([{ query: 'beta', timestamp: new Date().toISOString() }]),
    );
    spy.mockResolvedValue(successResponse('beta', 1));

    const user = userEvent.setup();
    render(<SearchPage />, { wrapper: Wrapper });
    const input = screen.getByTestId('search-input');
    await user.click(input);
    await user.click(await screen.findByTestId('search-recent-beta'));
    expect(input).toHaveValue('beta');
    await waitFor(() => expect(spy).toHaveBeenCalled(), { timeout: 1500 });
    expect(spy.mock.calls[spy.mock.calls.length - 1][0]).toBe('beta');
  });
});
