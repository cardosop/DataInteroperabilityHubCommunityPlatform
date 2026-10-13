/**
 * ScheduledIngestionCreatePage tests (openspec wire-databricks-dlt-movement
 * task 6.8, design D8) — the DATABRICKS_SOURCE form carries the
 * workspace+warehouse PICKER, never a placeholder http_path.
 *
 * UI contract pins:
 *  - DATABRICKS_SOURCE renders the picker (workspace + warehouse selects),
 *  - submitting stores the DERIVED `/sql/1.0/warehouses/{id}` http_path
 *    + the chosen workspace host in the source_config,
 *  - the placeholder `/sql/1.0/warehouses/placeholder` string NEVER
 *    appears (grep-pinned in source, submit-pinned in behavior),
 *  - submit is refused until a warehouse is picked (fail-closed — no
 *    placeholder substitution),
 *  - non-Databricks sources keep their existing behavior (regression).
 *
 * Sanctioned seams: the service modules + the create hook (the repo's
 * frontend convention — the form logic itself is real).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listWorkspaces } from '../../databricks/services/databricksService';
import { listWarehouses } from '../../databricks/services/warehouseService';
import { useCreateScheduledIngestion } from '../hooks/useScheduledIngestion';
import { ScheduledIngestionCreatePage } from './ScheduledIngestionCreatePage';

vi.mock('../../databricks/services/databricksService', () => ({
  listWorkspaces: vi.fn(),
}));

vi.mock('../../databricks/services/warehouseService', () => ({
  listWarehouses: vi.fn(),
}));

vi.mock('../hooks/useScheduledIngestion', () => ({
  useCreateScheduledIngestion: vi.fn(),
}));

const mockWorkspaces = vi.mocked(listWorkspaces);
const mockWarehouses = vi.mocked(listWarehouses);
const mockUseCreate = vi.mocked(useCreateScheduledIngestion);

const WORKSPACE_A = {
  id: 'ws-1',
  tenant: 't-1',
  name: 'Prod Workspace',
  host: 'prod.cloud.databricks.com',
  cloud: 'AWS',
  region: 'us-east-1',
  metastore_id: null,
  status: 'ACTIVE',
  status_display: 'Active',
  created_at: '2026-01-01T00:00:00Z',
};

const WAREHOUSE_1 = {
  warehouse_id: 'wh-1',
  name: 'analytics',
  state: 'RUNNING',
  serverless: true,
  size: null,
  auto_stop_mins: 30,
};

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/scheduled-ingestions/create']}>
        <ScheduledIngestionCreatePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockWorkspaces.mockResolvedValue([WORKSPACE_A]);
  mockWarehouses.mockResolvedValue([WAREHOUSE_1]);
  mockUseCreate.mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({ id: 'ing-1' }),
    isPending: false,
    error: null,
  } as never);
});

describe('ScheduledIngestionCreatePage — DATABRICKS_SOURCE', () => {
  it('renders the workspace+warehouse picker for DATABRICKS_SOURCE', async () => {
    renderPage();
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /source type/i }),
      'DATABRICKS_SOURCE',
    );

    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy(),
    );
  });

  it('stores the DERIVED http_path + host on submit', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: 'ing-1' });
    mockUseCreate.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    } as never);
    renderPage();

    await userEvent.type(screen.getByRole('textbox', { name: /name/i }), 'db-ing');
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /source type/i }),
      'DATABRICKS_SOURCE',
    );
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );
    await waitFor(() => expect(screen.getByRole('combobox', { name: /warehouse/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /warehouse/i }),
      'wh-1',
    );
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    const payload = mutateAsync.mock.calls[0][0];
    expect(payload.source_config).toEqual({
      host: 'prod.cloud.databricks.com',
      http_path: '/sql/1.0/warehouses/wh-1',
      catalog: 'main',
      schema: 'default',
    });
  });

  it('refuses submit until a warehouse is picked (no placeholder substitution)', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: 'ing-1' });
    mockUseCreate.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    } as never);
    renderPage();

    await userEvent.type(screen.getByRole('textbox', { name: /name/i }), 'db-ing');
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /source type/i }),
      'DATABRICKS_SOURCE',
    );
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it('the placeholder path string never appears', async () => {
    renderPage();
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /source type/i }),
      'DATABRICKS_SOURCE',
    );
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    expect(document.body.textContent).not.toContain('/sql/1.0/warehouses/placeholder');
  });

  it('renders the real S3 source fields when S3 is selected', async () => {
    renderPage(); // S3 is the default source type

    expect(screen.getByLabelText(/bucket/i)).toBeTruthy();
    expect(screen.getByLabelText(/prefix/i)).toBeTruthy();
    expect(screen.getByLabelText(/endpoint url/i)).toBeTruthy();
    expect(screen.getByLabelText(/access key id/i)).toBeTruthy();
    expect(screen.getByLabelText(/secret access key/i)).toBeTruthy();
  });

  it('stores the real S3 source_config on submit', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: 'ing-1' });
    mockUseCreate.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    } as never);
    renderPage();

    await userEvent.type(screen.getByRole('textbox', { name: /name/i }), 's3-ing');
    await userEvent.type(screen.getByLabelText(/bucket/i), 'my-bucket');
    await userEvent.type(screen.getByLabelText(/prefix/i), 'in/');
    await userEvent.type(screen.getByLabelText(/endpoint url/i), 'http://minio-test:9000');
    await userEvent.type(screen.getByLabelText(/access key id/i), 'minio');
    await userEvent.type(screen.getByLabelText(/secret access key/i), 'minio123');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    const payload = mutateAsync.mock.calls[0][0];
    expect(payload.source_type).toBe('S3');
    expect(payload.source_config).toEqual({
      bucket: 'my-bucket',
      prefix: 'in/',
      endpoint_url: 'http://minio-test:9000',
      access_key_id: 'minio',
      secret_access_key: 'minio123',
      region: 'us-east-1',
    });
  });

  it('refuses submit without bucket/credentials (fail-closed S3 guard)', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: 'ing-1' });
    mockUseCreate.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    } as never);
    renderPage();

    await userEvent.type(screen.getByRole('textbox', { name: /name/i }), 's3-ing');
    // fireEvent.submit bypasses jsdom's native constraint validation (which
    // would swallow the click) and exercises the React fail-closed guard.
    fireEvent.submit(screen.getByRole('textbox', { name: /name/i }).closest('form')!);

    expect(mutateAsync).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('Bucket, access key ID');
  });

  it('the placeholder bucket string never appears', async () => {
    renderPage();

    expect(document.body.textContent).not.toContain('placeholder-bucket');
  });
});
