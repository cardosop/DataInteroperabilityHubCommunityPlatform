/**
 * Tests for AssetCreatePage — unified adaptive form.
 * TDD: Tests written FIRST.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AssetCreatePage } from '../AssetCreatePage';
import { ToastProvider } from '../../../../shared/components/Toast';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={['/assets/create']}>
          <Routes>
            <Route path="/assets/create" element={<AssetCreatePage />} />
            <Route path="/assets/:id" element={<div data-testid="asset-detail">Asset Detail</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('AssetCreatePage — rendering', () => {
  it('renders page heading', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /create asset/i })).toBeInTheDocument();
  });

  it('renders name and key fields', () => {
    renderPage();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/key/i)).toBeInTheDocument();
  });

  it('renders visibility dropdown', () => {
    renderPage();
    expect(screen.getByLabelText(/visibility/i)).toBeInTheDocument();
  });

  it('renders collapsible data file toggle', () => {
    renderPage();
    expect(screen.getByText(/add data file/i)).toBeInTheDocument();
  });

  it('renders collapsible contract toggle', () => {
    renderPage();
    expect(screen.getByText(/add contract/i)).toBeInTheDocument();
  });

  it('renders submit button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument();
  });

  it('renders CreateAssetSummary showing "Will create: Asset"', () => {
    renderPage();
    expect(screen.getByText(/will create.*asset/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Key auto-populate from name
// ---------------------------------------------------------------------------

describe('AssetCreatePage — key auto-populate', () => {
  it('auto-populates key from name via slugify', async () => {
    renderPage();
    const user = userEvent.setup();

    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'My Test Asset');

    const keyInput = screen.getByLabelText(/key/i) as HTMLInputElement;
    expect(keyInput.value).toBe('my-test-asset');
  });
});

// ---------------------------------------------------------------------------
// Collapsible sections
// ---------------------------------------------------------------------------

describe('AssetCreatePage — collapsible sections', () => {
  it('data file section is collapsed by default', () => {
    renderPage();
    // FileUpload should not be visible initially
    expect(screen.queryByText(/drag and drop/i)).not.toBeInTheDocument();
  });

  it('clicking "Add data file" expands the section', async () => {
    renderPage();
    const user = userEvent.setup();

    const toggle = screen.getByText(/add data file/i);
    await user.click(toggle);

    // After expanding, some upload UI should appear
    await waitFor(() => {
      expect(toggle.closest('[aria-expanded]')?.getAttribute('aria-expanded')).toBe('true');
    });
  });

  it('clicking "Add contract" expands the contract section', async () => {
    renderPage();
    const user = userEvent.setup();

    const toggle = screen.getByText(/add contract/i);
    await user.click(toggle);

    await waitFor(() => {
      expect(toggle.closest('[aria-expanded]')?.getAttribute('aria-expanded')).toBe('true');
    });
  });
});

// ---------------------------------------------------------------------------
// Summary updates
// ---------------------------------------------------------------------------

describe('AssetCreatePage — summary updates', () => {
  it('summary shows "Asset + Contract" after expanding contract section and entering content', async () => {
    renderPage();
    const user = userEvent.setup();

    // Expand contract section
    await user.click(screen.getByText(/add contract/i));

    // Wait for contract reader to appear, then enter content
    await waitFor(() => {
      const textarea = screen.getByLabelText(/contract content/i);
      fireEvent.change(textarea, {
        target: { value: 'apiVersion: odcs/v3\nkind: DataContract\nid: test' },
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/will create.*asset.*contract/i)).toBeInTheDocument();
    });
  });
});
