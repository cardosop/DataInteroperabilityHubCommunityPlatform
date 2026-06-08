/**
 * DatasetReplaceDataModal tests — Phase 260.4.D.
 *
 * Exercises the modal-level integration:
 *   - mounts FileUpload
 *   - calls POST /datasets/{id}/refresh-from-file/ when a file lands
 *   - delivers the response (dataset + drift) to onSuccess
 *   - Cancel button closes without firing the API
 *
 * The FileUpload component is replaced by a synthetic stub that
 * exposes a button to trigger ``onUploadComplete`` directly. This is
 * a surgical isolation of the upload INFRASTRUCTURE (multipart
 * pipeline, S3 presign, scan polling) — the modal's BUSINESS LOGIC
 * (refresh mutation, onSuccess wiring) runs unmocked. FileUpload's
 * own integration is covered by ``FileUpload.test.tsx`` so we don't
 * double-cover its surface here.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { HttpClient } from '../../../shared/types/api';
import type { File as AppFile } from '../../../shared/types/files';
import { ToastProvider } from '../../../shared/components/Toast';
import { DatasetReplaceDataModal } from './DatasetReplaceDataModal';

vi.mock('../../../shared/api/client');
// R1 audit GAP-D — replace FileUpload with a synthetic stub that
// exposes ``onUploadComplete`` as a clickable button. This isolates
// the modal's integration with the refresh mutation from the
// upload pipeline's infrastructure. The real FileUpload's contract
// is covered by FileUpload.test.tsx.
vi.mock('../../files/components/FileUpload', () => {
  return {
    FileUpload: ({
      onUploadComplete,
    }: {
      onUploadComplete?: (file: AppFile) => void;
    }) => (
      <div data-testid="file-upload-stub">
        <span>Drag and drop a file here</span>
        <button
          type="button"
          data-testid="file-upload-trigger-success"
          onClick={() => {
            const file: AppFile = {
              id: '11111111-2222-3333-4444-555555555555',
              name: 'refreshed.csv',
              content_type: 'text/csv',
              size: 100,
              storage_path: 't/x/refreshed.csv',
              status: 'COMPLETED',
              scan_status: 'CLEAN',
              created_at: '2025-01-01T00:00:00Z',
              updated_at: '2025-01-01T00:00:00Z',
              created_by: 'user-1',
              tenant_id: 'tenant-1',
            };
            onUploadComplete?.(file);
          }}
        >
          Simulate upload complete
        </button>
      </div>
    ),
  };
});

import { apiClient } from '../../../shared/api/client';

const DATASET_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

describe('DatasetReplaceDataModal (Phase 260.4.D)', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>{children}</MemoryRouter>
        </ToastProvider>
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
    mockClient = apiClient.getClient();
    vi.mocked(mockClient.get).mockClear();
    vi.mocked(mockClient.post).mockClear();
  });

  it('does not render when open=false', () => {
    render(
      <DatasetReplaceDataModal
        open={false}
        datasetId={DATASET_ID}
        datasetName="My Dataset"
        onCancel={() => {}}
        onSuccess={() => {}}
      />,
      { wrapper },
    );
    expect(screen.queryByTestId('dataset-replace-modal-body')).toBeNull();
  });

  it('renders FileUpload and the explainer when open', () => {
    render(
      <DatasetReplaceDataModal
        open={true}
        datasetId={DATASET_ID}
        datasetName="My Dataset"
        onCancel={() => {}}
        onSuccess={() => {}}
      />,
      { wrapper },
    );
    expect(screen.getByTestId('dataset-replace-modal-body')).toBeInTheDocument();
    expect(screen.getByText(/upload a new file to create the next version/i)).toBeInTheDocument();
    expect(screen.getByText(/drag and drop a file here/i)).toBeInTheDocument();
  });

  it('Cancel closes without firing the refresh API', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(
      <DatasetReplaceDataModal
        open={true}
        datasetId={DATASET_ID}
        datasetName="My Dataset"
        onCancel={onCancel}
        onSuccess={() => {}}
      />,
      { wrapper },
    );

    await user.click(screen.getByTestId('dataset-replace-cancel-btn'));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(vi.mocked(mockClient.post)).not.toHaveBeenCalledWith(
      expect.stringContaining('/refresh-from-file/'),
      expect.anything(),
    );
  });

  it('R1 audit GAP-D — onUploadComplete fires refresh API and delivers response to onSuccess', async () => {
    // R1 audit: the modal's load-bearing claim is "upload IS the
    // refresh trigger — no separate Continue CTA". Without this
    // test the integration breaks silently if FileUpload's
    // ``onUploadComplete`` callback wiring regresses. The
    // synthetic FileUpload stub exposes a button that fires the
    // callback with a deterministic file payload; the modal then
    // calls the refresh mutation through real React Query, and the
    // mocked apiClient.post returns the canonical response.
    const onSuccess = vi.fn();
    const refreshResponse = {
      dataset: {
        id: 'aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        name: 'Refreshed.csv',
        format: 'CSV',
        version: 2,
      },
      schema_drift: {
        has_contract: true,
        contract_id: 'c1',
        detected: true,
        severity: 'WARN',
        missing_fields: [],
        extra_fields: ['bonus'],
        type_mismatches: [],
        structural_incompatibility: false,
      },
    };
    vi.mocked(mockClient.post).mockImplementation((url: string) => {
      if (url.includes('/refresh-from-file/')) {
        return Promise.resolve({ data: refreshResponse }) as never;
      }
      return Promise.reject(new Error(`unexpected POST ${url}`)) as never;
    });

    const user = userEvent.setup();
    render(
      <DatasetReplaceDataModal
        open={true}
        datasetId={DATASET_ID}
        datasetName="My Dataset"
        onCancel={() => {}}
        onSuccess={onSuccess}
      />,
      { wrapper },
    );

    // Trigger the upload-complete callback exposed by the FileUpload stub.
    await user.click(screen.getByTestId('file-upload-trigger-success'));

    // The modal MUST call the refresh API with the new file's id.
    await waitFor(() => {
      expect(vi.mocked(mockClient.post)).toHaveBeenCalledWith(
        expect.stringContaining(`datasets/${DATASET_ID}/refresh-from-file/`),
        { file_id: '11111111-2222-3333-4444-555555555555' },
      );
    });

    // And must deliver the response (dataset + drift) to onSuccess.
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1);
      expect(onSuccess).toHaveBeenCalledWith(refreshResponse);
    });
  });
});
