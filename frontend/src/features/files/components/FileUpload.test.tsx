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

// Phase 260.3.F.3 — the resume CTA routes picks through
// useMultipartUpload.resume / computeFingerprint. The hoisted mocks keep
// the component wiring testable without exercising MultipartUploader
// (covered by utils/multipartUploader.test.ts).
const resumeMocks = vi.hoisted(() => ({
  resume: vi.fn(),
  computeFingerprint: vi.fn(),
}));

vi.mock('../hooks/useMultipartUpload', () => ({
  useMultipartUpload: () => ({
    upload: vi.fn(),
    resume: resumeMocks.resume,
    computeFingerprint: resumeMocks.computeFingerprint,
    isPending: false,
    error: null,
    reset: vi.fn(),
  }),
}));

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
  resumeMocks.resume.mockReset();
  resumeMocks.computeFingerprint.mockReset();
  resumeMocks.computeFingerprint.mockReturnValue(null);
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

describe('FileUpload — Phase 260.3.F.3 resume CTA', () => {
  it('renders a Resume button per checkpoint entry', () => {
    saveUploadCheckpoint(makeCheckpoint({ fingerprint: 'fp-A' }));
    render(<FileUpload />, { wrapper });
    expect(screen.getByTestId('resume-btn-fp-A')).toBeInTheDocument();
    expect(screen.getByTestId('resume-btn-fp-A')).toHaveTextContent('Resume');
  });

  it('resume pick with a mismatched file renders the inline mismatch error and never calls resume', async () => {
    vi.useRealTimers();
    const user = userEvent.setup();
    resumeMocks.computeFingerprint.mockReturnValue('other-fp');
    // Relative timestamps: listResumableUploads prunes stale checkpoints,
    // so a FIXED_NOW-anchored entry expires under real timers.
    saveUploadCheckpoint(
      makeCheckpoint({ fingerprint: 'fp-A', updatedAt: Date.now() - 100 }),
    );
    render(<FileUpload />, { wrapper });

    await user.click(screen.getByTestId('resume-btn-fp-A'));
    await user.upload(
      screen.getByTestId('file-upload-input'),
      new File(['x'], 'different.csv', { type: 'text/csv' }),
    );

    await waitFor(() => {
      expect(screen.getByTestId('resume-error')).toHaveTextContent(/does not match/i);
    });
    expect(resumeMocks.resume).not.toHaveBeenCalled();
    // The rejected pick must not leave the dropzone stuck in the
    // "Uploading..." state behind the mismatch error.
    expect(screen.getByTestId('file-upload-dropzone')).toHaveAttribute(
      'data-upload-state',
      'idle',
    );
  });

  it('resume pick with a matching file resumes the checkpoint and clears the prompt', async () => {
    vi.useRealTimers();
    const user = userEvent.setup();
    resumeMocks.computeFingerprint.mockReturnValue('fp-A');
    resumeMocks.resume.mockResolvedValue({ id: 'file-A' });
    // Relative timestamps: listResumableUploads prunes stale checkpoints,
    // so a FIXED_NOW-anchored entry expires under real timers. totalSize
    // matches the 1-byte File below — the component's size pre-check
    // rejects a pick whose size differs from the checkpoint.
    saveUploadCheckpoint(
      makeCheckpoint({
        fingerprint: 'fp-A',
        totalSize: 1,
        updatedAt: Date.now() - 100,
      }),
    );
    const onUploadComplete = vi.fn();
    render(<FileUpload onUploadComplete={onUploadComplete} />, { wrapper });

    await user.click(screen.getByTestId('resume-btn-fp-A'));
    await user.upload(
      screen.getByTestId('file-upload-input'),
      new File(['x'], 'big.csv', { type: 'text/csv' }),
    );

    await waitFor(() => {
      expect(resumeMocks.resume).toHaveBeenCalledTimes(1);
    });
    const [fileArg, checkpointArg] = resumeMocks.resume.mock.calls[0];
    expect((fileArg as File).name).toBe('big.csv');
    expect((checkpointArg as UploadCheckpoint).fingerprint).toBe('fp-A');
    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalled();
    });
    // The consumed checkpoint removes the prompt.
    await waitFor(() => {
      expect(screen.queryByTestId('file-upload-resume-prompt')).toBeNull();
    });
  });
});
