/**
 * close-test-coverage-gaps 3.2 — ProcessorAgreementsPage suite
 * (Phase 232.6.11).
 *
 * Real page + real hooks (useTranslation, ErrorDisplay,
 * ListPageSkeleton, MemoryRouter for the back-link) + real crypto.subtle
 * for the file-hash path; only the API client and window.confirm are
 * test doubles (the CpoCostOverviewPage pattern).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProcessorAgreementsPage } from '../ProcessorAgreementsPage';

// vi.hoisted: the page captures its client at MODULE level (3.2 fix),
// so the mock factory runs during import — before the consts below
// exist. A single stable client object mirrors the real singleton
// (referential stability is part of the contract the page relies on).
const { mockGet, mockPost, mockPatch, mockDelete } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPatch: vi.fn(),
  mockDelete: vi.fn(),
}));

vi.mock('../../../../shared/api/client', () => {
  const client = { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete };
  return { apiClient: { getClient: () => client } };
});

const PROCESSOR = { id: 'proc-1', name: 'Acme Processing', legal_name: 'Acme GmbH' };
const AGREEMENT = {
  id: 'agr-1',
  processor: 'proc-1',
  processor_name: 'Acme Processing',
  agreement_type: 'DPA',
  document_uri: 'https://docs.example.com/dpa.pdf',
  document_hash: 'ab'.repeat(32),
  effective_from: '2026-01-01',
  expires_on: null,
  status: 'ACTIVE',
};

function installLoadMock(
  processors = [PROCESSOR],
  agreements = [AGREEMENT],
  shape: 'paged' | 'bare' = 'paged',
) {
  const wrap = <T,>(rows: T[]) => (shape === 'paged' ? { results: rows } : rows);
  mockGet.mockImplementation((url: string) => {
    if (url.includes('processor-agreements/processors/')) {
      return Promise.resolve({ data: wrap(processors) });
    }
    if (url.includes('processor-agreements/processor-agreements/')) {
      return Promise.resolve({ data: wrap(agreements) });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ProcessorAgreementsPage />
    </MemoryRouter>,
  );
}

async function waitForLoaded() {
  await waitFor(() => {
    expect(screen.getByRole('heading', { name: 'Processor agreements' })).toBeDefined();
  });
}

describe('ProcessorAgreementsPage (close-test-coverage-gaps 3.2)', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPatch.mockReset();
    mockDelete.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the list skeleton while the two inventories load', () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    // ListPageSkeleton renders 8 skeleton rows.
    expect(screen.getAllByTestId('skeleton-row')).toHaveLength(8);
  });

  it('shows the error display when the initial load fails', async () => {
    mockGet.mockRejectedValue(new Error('governance API down'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('An error occurred')).toBeDefined();
    });
  });

  it('loads both inventories with the exact wire URLs and renders rows', async () => {
    installLoadMock();
    renderPage();
    await waitForLoaded();

    expect(mockGet).toHaveBeenCalledWith('processor-agreements/processors/');
    expect(mockGet).toHaveBeenCalledWith('processor-agreements/processor-agreements/');

    // Processor row: name · legal_name, in the list.
    expect(screen.getByText(/Acme Processing · Acme GmbH/)).toBeDefined();
    // Agreement row: scope to the ACTIVE row ('DPA' also appears as a
    // Type-select option).
    const agreementRow = screen.getByText('ACTIVE').closest('tr') as HTMLTableRowElement;
    expect(within(agreementRow).getByText('DPA')).toBeDefined();
    expect(within(agreementRow).getByText('Acme Processing')).toBeDefined();
    expect(within(agreementRow).getByText('—')).toBeDefined();
    // The agreement form's processor select defaults to the first row.
    const select = screen.getByLabelText('Processor') as HTMLSelectElement;
    expect(select.value).toBe('proc-1');
  });

  it('unwraps a bare-array response (non-paginated backend)', async () => {
    installLoadMock([PROCESSOR], [AGREEMENT], 'bare');
    renderPage();
    await waitForLoaded();
    const agreementRow = screen.getByText('ACTIVE').closest('tr') as HTMLTableRowElement;
    expect(within(agreementRow).getByText('DPA')).toBeDefined();
    expect(within(agreementRow).getByText('Acme Processing')).toBeDefined();
  });

  it('adds a processor with the exact POST body and reloads', async () => {
    installLoadMock();
    mockPost.mockResolvedValue({ data: PROCESSOR });
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    await user.type(screen.getByLabelText('Name'), 'New Co');
    await user.type(screen.getByLabelText('Legal name (optional)'), 'New Co LLC');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('processor-agreements/processors/', {
        name: 'New Co',
        legal_name: 'New Co LLC',
      });
    });
    // Reload after create: the load GETs fire again.
    expect(mockGet).toHaveBeenCalledTimes(4);
  });

  it('does not POST a processor with an empty name', async () => {
    installLoadMock();
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('deletes a processor only after window.confirm', async () => {
    installLoadMock();
    mockDelete.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(deleteButtons[0]);
    expect(mockDelete).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    await user.click(deleteButtons[0]);
    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('processor-agreements/processors/proc-1/');
    });
  });

  it('registers an agreement with the exact wire shape (region uppercased)', async () => {
    installLoadMock();
    mockPost.mockResolvedValue({ data: AGREEMENT });
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    await user.type(screen.getByLabelText('Document URL'), 'https://docs.example.com/dpa2.pdf');
    const hashInput = screen.getByLabelText('SHA-256 (hex)') as HTMLInputElement;
    await user.clear(hashInput);
    await user.type(hashInput, 'AB'.repeat(32));
    await user.type(screen.getByLabelText('Region hint (BAA)'), 'us');
    await user.click(screen.getByRole('button', { name: 'Save agreement' }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledTimes(1);
    });
    expect(mockPost).toHaveBeenCalledWith('processor-agreements/processor-agreements/', {
      processor: 'proc-1',
      agreement_type: 'DPA',
      document_uri: 'https://docs.example.com/dpa2.pdf',
      document_hash: 'ab'.repeat(32),
      effective_from: new Date().toISOString().slice(0, 10),
      expires_on: null,
      sub_processors_declared: [],
      transfer_mechanism_summary: '',
      registration_reference: '',
      jurisdiction_region: 'US',
    });
  });

  it('computes the SHA-256 hex from a picked file (real crypto.subtle)', async () => {
    installLoadMock();
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    const file = new File(['hello'], 'dpa.txt', { type: 'text/plain' });
    await user.upload(screen.getByLabelText(/compute hash from file/i), file);

    await waitFor(() => {
      expect((screen.getByLabelText('SHA-256 (hex)') as HTMLInputElement).value).toBe(
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
      );
    });
  });

  it('edits an agreement with the exact PATCH body and closes the panel', async () => {
    installLoadMock();
    mockPatch.mockResolvedValue({ data: AGREEMENT });
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    await user.click(screen.getByRole('button', { name: 'Edit' }));
    const editPanel = screen.getByRole('heading', { name: 'Edit agreement' }).closest('div') as HTMLElement;

    const region = screen.getByLabelText('Region hint') as HTMLInputElement;
    await user.clear(region);
    await user.type(region, 'DE');
    // The page has two Save buttons (processor form + edit panel) —
    // scope to the edit panel.
    await user.click(within(editPanel).getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('processor-agreements/processor-agreements/agr-1/', {
        expires_on: null,
        transfer_mechanism_summary: '',
        registration_reference: '',
        jurisdiction_region: 'DE',
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Edit agreement' })).toBeNull();
    });
  });

  it('deletes an agreement after confirm', async () => {
    installLoadMock();
    mockDelete.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderPage();
    await waitForLoaded();

    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const row = screen.getByText('ACTIVE').closest('tr') as HTMLTableRowElement;
    await user.click(within(row).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('processor-agreements/processor-agreements/agr-1/');
    });
  });

  it('renders an empty processor select when no processors exist', async () => {
    installLoadMock([], []);
    renderPage();
    await waitForLoaded();
    const select = screen.getByLabelText('Processor') as HTMLSelectElement;
    expect(select.options).toHaveLength(0);
    // The list section renders no placeholder text — just the empty ul.
    expect(screen.queryByText('No processors')).toBeNull();
    expect(screen.getByText(/Register processors/)).toBeDefined();
  });
});
