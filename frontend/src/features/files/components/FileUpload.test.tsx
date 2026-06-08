/**
 * FileUpload tests — Phase 260.3.F resume-prompt UX.
 *
 * Behavioural coverage for the resume prompt + Discard CTA. The
 * actual ``MultipartUploader`` orchestration is covered by
 * ``utils/multipartUploader.test.ts``; here we verify the component-
 * level wiring:
 *
 *   - prompt renders ONLY when ``listResumableUploads`` returns ≥1
 *     entry (real localStorage; no mocks of the storage layer)
 *   - prompt entry shows file name + N/M parts progress text
 *   - "Discard" clears the checkpoint and removes the entry from
 *     the prompt without affecting siblings
 *   - prompt is absent on first load with no checkpoints
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { FileUpload } from './FileUpload';
import { ToastProvider } from '../../../shared/components/Toast';
import { useAuthStore } from '../../auth/store/authStore';
import {
  saveUploadCheckpoint,
  type UploadCheckpoint,
} from '../utils/multipartResumeStorage';

const FIXED_NOW = Date.parse('2026-05-05T10:00:00Z');

function makeCheckpoint(overrides: Partial<UploadCheckpoint> = {}): UploadCheckpoint {
  return {
    fingerprint: 'fp-A',
    fileId: 'file-A',
    uploadId: 'mpu-A',
    fileName: 'big.csv',
    contentType: 'text/csv',
    totalSize: 200 * 1024 * 1024,
    chunkSize: 50 * 1024 * 1024,
    chunkCount: 4,
    completedParts: [
      { partNumber: 1, etag: '"e1"' },
      { partNumber: 2, etag: '"e2"' },
    ],
    startedAt: FIXED_NOW - 5000,
    updatedAt: FIXED_NOW - 5000,
    ...overrides,
  };
}

function setUser(id = 'user-1') {
  useAuthStore.setState({
    user: {
      id,
      email: 'user@example.com',
      name: 'Test User',
      roles: [],
      tenant_id: 't1',
      is_active: true,
    },
    active_tenant_id: null,
    isAuthenticated: true,
    isLoading: false,
    error: null,
  });
}

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  setUser();
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
  // Manual `afterEach` hooks run BEFORE RTL's auto-cleanup, so the
  // tree is still mounted when this runs. Resetting the Zustand
  // store outside act() schedules a synchronous re-render of the
  // mounted FileUpload (it subscribes to `user.id`), which leaks an
  // act warning. Commit the reset under act() so React can track the
  // re-render in the same scope.
  act(() => {
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });
});

describe('FileUpload — Phase 260.3.F resume prompt', () => {
  it('renders no resume prompt on first load', () => {
    render(<FileUpload />, { wrapper });
    expect(screen.queryByTestId('file-upload-resume-prompt')).toBeNull();
  });

  it('renders the prompt with file name + parts progress when a checkpoint exists', () => {
    saveUploadCheckpoint(makeCheckpoint());
    render(<FileUpload />, { wrapper });
    const prompt = screen.getByTestId('file-upload-resume-prompt');
    expect(prompt).toHaveTextContent('Resume previous upload?');
    expect(prompt).toHaveTextContent('big.csv');
    // 2 of 4 parts uploaded -> 50%.
    expect(prompt).toHaveTextContent('2/4 parts uploaded (50%)');
  });

  it('shows multiple resume entries sorted newest-first', () => {
    saveUploadCheckpoint(
      makeCheckpoint({ fingerprint: 'fp-1', fileName: 'older.csv', updatedAt: FIXED_NOW - 5_000 })
    );
    saveUploadCheckpoint(
      makeCheckpoint({ fingerprint: 'fp-2', fileName: 'newer.csv', updatedAt: FIXED_NOW - 100 })
    );
    render(<FileUpload />, { wrapper });
    const items = screen.getAllByText(/\.csv$/);
    expect(items.map((n) => n.textContent)).toEqual(['newer.csv', 'older.csv']);
  });

  it('Discard removes the checkpoint and the prompt entry', async () => {
    vi.useRealTimers();
    const now = Date.now();
    const user = userEvent.setup();
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-1', fileName: 'a.csv', updatedAt: now - 1000 }));
    saveUploadCheckpoint(
      makeCheckpoint({ fingerprint: 'fp-2', fileName: 'b.csv', updatedAt: now - 100 })
    );
    render(<FileUpload />, { wrapper });

    const discardA = screen.getByTestId('discard-btn-fp-1');
    await user.click(discardA);

    await waitFor(() => {
      expect(screen.queryByTestId('discard-btn-fp-1')).toBeNull();
    });
    expect(screen.getByTestId('discard-btn-fp-2')).toBeInTheDocument();
  });

  it('Discard hides the prompt entirely when the last checkpoint is removed', async () => {
    vi.useRealTimers();
    const now = Date.now();
    const user = userEvent.setup();
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-only', updatedAt: now - 100 }));
    render(<FileUpload />, { wrapper });

    expect(screen.getByTestId('file-upload-resume-prompt')).toBeInTheDocument();
    await user.click(screen.getByTestId('discard-btn-fp-only'));
    await waitFor(() => {
      expect(screen.queryByTestId('file-upload-resume-prompt')).toBeNull();
    });
  });
});
