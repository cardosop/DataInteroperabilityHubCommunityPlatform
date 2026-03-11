/**
 * DatasetCreatePage Unit Tests
 * Per task 29.68.6.1. Flow selector (none | existing | create_new), AssetPicker, create_new.
 * Uses axios mock for controlled API responses; real hooks and components.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../../shared/components/Toast';
import { DatasetCreatePage } from './DatasetCreatePage';

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

vi.mock('../../files/components/FileUpload', () => ({
  FileUpload: ({
    onUploadComplete,
  }: {
    onUploadComplete: (file: { id: string; name: string; size: number }) => void;
  }) => (
    <div className="file-upload" data-testid="file-upload">
      <button
        type="button"
        onClick={() =>
          onUploadComplete({
            id: 'file-123',
            name: 'test.csv',
            size: 1024,
          })
        }
        data-testid="mock-upload-trigger"
      >
        Simulate upload
      </button>
    </div>
  ),
}));

import { apiClient } from '../../../shared/api/client';

describe('DatasetCreatePage', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children, initialEntries = ['/datasets/create'] }: { children: ReactNode; initialEntries?: string[] }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={initialEntries}>
            <Routes>
              <Route path="/datasets/create" element={children} />
              <Route path="/datasets/:id" element={<div data-testid="dataset-detail" />} />
              <Route path="/assets/:id" element={<div data-testid="asset-detail" />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
  });

  it('renders flow selector with none, existing, create_new options', () => {
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    expect(screen.getByRole('group', { name: /asset linking mode/i })).toBeInTheDocument();
    expect(screen.getByTestId('flow-none')).toBeInTheDocument();
    expect(screen.getByTestId('flow-existing')).toBeInTheDocument();
    expect(screen.getByTestId('flow-create-new')).toBeInTheDocument();
    expect(screen.getByText(/create dataset only/i)).toBeInTheDocument();
    expect(screen.getByText(/link to existing asset/i)).toBeInTheDocument();
    expect(screen.getByText(/create new asset and link/i)).toBeInTheDocument();
  });

  it('defaults to none flow', () => {
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    expect(screen.getByTestId('flow-none')).toBeChecked();
    expect(screen.getByTestId('flow-existing')).not.toBeChecked();
    expect(screen.getByTestId('flow-create-new')).not.toBeChecked();
  });

  it('shows AssetPicker when existing flow selected', async () => {
    const user = userEvent.setup();
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('flow-existing'));

    expect(screen.getByTestId('asset-picker')).toBeInTheDocument();
  });

  it('shows create_new key/name inputs when create_new flow selected', async () => {
    const user = userEvent.setup();
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('flow-create-new'));

    expect(screen.getByTestId('create-new-key')).toBeInTheDocument();
    expect(screen.getByTestId('create-new-name')).toBeInTheDocument();
  });

  it('initializes linkMode from URL param ?linkMode=create_new', () => {
    render(<DatasetCreatePage />, {
      wrapper: (props) => wrapper({ ...props, initialEntries: ['/datasets/create?linkMode=create_new'] }),
    });

    expect(screen.getByTestId('flow-create-new')).toBeChecked();
  });

  it('initializes linkMode from URL param ?linkMode=existing', () => {
    render(<DatasetCreatePage />, {
      wrapper: (props) => wrapper({ ...props, initialEntries: ['/datasets/create?linkMode=existing'] }),
    });

    expect(screen.getByTestId('flow-existing')).toBeChecked();
  });

  it('submit button disabled when no file uploaded', () => {
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    expect(screen.getByTestId('btn-create-dataset')).toBeDisabled();
  });

  it('submit button enabled when file uploaded and flow=none', async () => {
    const user = userEvent.setup();
    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('mock-upload-trigger'));

    await waitFor(() => {
      expect(screen.getByTestId('btn-create-dataset')).toBeEnabled();
    });
  });

  it('create_new flow: submit button enabled when file, key, name filled', async () => {
    const user = userEvent.setup();
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' },
      status: 201,
    });

    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('mock-upload-trigger'));
    await user.click(screen.getByTestId('flow-create-new'));

    await waitFor(() => {
      expect(screen.getByTestId('create-new-key')).toHaveValue('test');
    });

    await user.clear(screen.getByTestId('create-new-key'));
    await user.type(screen.getByTestId('create-new-key'), 'my-asset');
    await user.clear(screen.getByTestId('create-new-name'));
    await user.type(screen.getByTestId('create-new-name'), 'My Asset');

    await waitFor(() => {
      expect(screen.getByTestId('btn-create-dataset')).toBeEnabled();
    });
  });

  it('existing flow: calls create dataset API with file_id and asset_id on submit', async () => {
    const user = userEvent.setup();
    const mockAssets = { results: [{ id: 'asset-1', name: 'Test Asset', key: 'test-asset' }], count: 1 };
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({ data: mockAssets });
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { id: 'ds-1', name: 'Dataset', file_id: 'file-123', asset_id: 'asset-1' },
      status: 201,
    });

    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('mock-upload-trigger'));
    await user.click(screen.getByTestId('flow-existing'));

    await waitFor(() => expect(screen.getByTestId('asset-picker')).toBeInTheDocument());

    const pickerInput = screen.getByRole('combobox', { name: /select asset/i });
    await user.click(pickerInput);
    await waitFor(() => expect(screen.getByText('Test Asset')).toBeInTheDocument());
    await user.click(screen.getByText('Test Asset'));

    await waitFor(() => expect(screen.getByTestId('btn-create-dataset')).toBeEnabled());
    await user.click(screen.getByTestId('btn-create-dataset'));

    await waitFor(() => {
      const postCalls = vi.mocked(mockAxiosInstance.post).mock.calls;
      const datasetCreateCall = postCalls.find((c) => String(c[0] ?? '').includes('datasets') && !String(c[0] ?? '').includes('data-first'));
      expect(datasetCreateCall).toBeDefined();
      expect(datasetCreateCall?.[1]).toMatchObject({
        file_id: 'file-123',
        asset_id: 'asset-1',
      });
    });
  });

  it('create_new flow: calls data-first API on submit', async () => {
    const user = userEvent.setup();
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' },
      status: 201,
    });

    render(<DatasetCreatePage />, { wrapper: (props) => wrapper({ ...props }) });

    await user.click(screen.getByTestId('mock-upload-trigger'));
    await user.click(screen.getByTestId('flow-create-new'));

    await waitFor(() => {
      expect(screen.getByTestId('btn-create-dataset')).toBeEnabled();
    });

    await user.click(screen.getByTestId('btn-create-dataset'));

    await waitFor(() => {
      const postCalls = vi.mocked(mockAxiosInstance.post).mock.calls;
      const dataFirstCall = postCalls.find((c) => String(c[0] ?? '').includes('data-first'));
      expect(dataFirstCall).toBeDefined();
      expect(dataFirstCall?.[1]).toMatchObject({
        file_id: 'file-123',
        key: expect.any(String),
        name: expect.any(String),
      });
    });
  });
});
