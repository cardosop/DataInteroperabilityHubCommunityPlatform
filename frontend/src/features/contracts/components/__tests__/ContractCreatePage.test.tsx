/**
 * Tests for ContractCreatePage — unified contract creation with
 * auto-detection and branched submit (ODPS workflow vs sync).
 *
 * TDD: Tests written FIRST.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ContractCreatePage } from '../ContractCreatePage';
import { ToastProvider } from '../../../../shared/components/Toast';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const odcsYaml = [
  'apiVersion: odcs/v3',
  'kind: DataContract',
  'id: test-contract',
  'name: Test Contract',
].join('\n');

const odpsJson = JSON.stringify({
  schema: 'https://opendataproducts.org/schema/v4.1',
  version: '4.1',
  product: { details: { en: { productID: 'p', name: 'P' } } },
});

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage(initialPath = '/contracts/create') {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/contracts/create" element={<ContractCreatePage />} />
            <Route path="/contracts/:id" element={<div data-testid="contract-detail">Contract Detail</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('ContractCreatePage — rendering', () => {
  it('renders the page with title and ContractFileReader', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /create contract/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/contract content/i)).toBeInTheDocument();
  });

  it('renders breadcrumbs with Contracts link', () => {
    renderPage();
    expect(screen.getByText('Contracts')).toBeInTheDocument();
  });

  it('renders a submit button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument();
  });

  it('submit button is disabled when no content', () => {
    renderPage();
    const btn = screen.getByRole('button', { name: /create/i });
    expect(btn).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Auto-detection display
// ---------------------------------------------------------------------------

describe('ContractCreatePage — auto-detection', () => {
  it('shows ODCS detection badge when ODCS content is entered', async () => {
    renderPage();
    const textarea = screen.getByLabelText(/contract content/i);
    fireEvent.change(textarea, { target: { value: odcsYaml } });

    await waitFor(() => {
      expect(screen.getByText(/ODCS/)).toBeInTheDocument();
    });
  });

  it('shows ODPS detection badge when ODPS content is entered', async () => {
    renderPage();
    const textarea = screen.getByLabelText(/contract content/i);
    fireEvent.change(textarea, { target: { value: odpsJson } });

    await waitFor(() => {
      expect(screen.getByText(/ODPS/)).toBeInTheDocument();
    });
  });

  it('enables submit button after content is entered', async () => {
    renderPage();
    const textarea = screen.getByLabelText(/contract content/i);
    fireEvent.change(textarea, { target: { value: odcsYaml } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create/i })).not.toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Form fields
// ---------------------------------------------------------------------------

describe('ContractCreatePage — optional fields', () => {
  it('renders name input field', () => {
    renderPage();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it('renders description input field', () => {
    renderPage();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Asset linking via query param
// ---------------------------------------------------------------------------

describe('ContractCreatePage — asset_id query param', () => {
  it('shows linked asset indicator when asset_id is in URL', () => {
    renderPage('/contracts/create?asset_id=abc-123');
    expect(screen.getByText(/linked.*asset|asset.*abc-123/i)).toBeInTheDocument();
  });
});
