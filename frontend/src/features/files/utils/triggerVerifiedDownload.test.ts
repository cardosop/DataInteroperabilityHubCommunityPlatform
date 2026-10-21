/**
 * triggerVerifiedDownload tests — Phase 260.3.G UI integration.
 *
 * Behavioural test for the small wrapper that ties
 * :func:`downloadFileWithVerification` to a browser-native save flow:
 *   - on success — the wrapper creates a Blob URL + clicks an
 *     ``<a download>`` element so the user gets a save-as dialog,
 *   - on mismatch — the wrapper rethrows ``ChecksumMismatchError`` so
 *     the FileListPage can surface a toast.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ChecksumMismatchError } from './downloadFileWithVerification';
import { triggerVerifiedDownload } from './triggerVerifiedDownload';

const ABC_SHA256 = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

describe('triggerVerifiedDownload', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    createObjectURLMock = vi.fn(() => 'blob:fake-object-url');
    revokeObjectURLMock = vi.fn();
    URL.createObjectURL = createObjectURLMock as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLMock as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('creates a save-as anchor and triggers click on a verified download', async () => {
    const httpMock = vi.mocked(apiClient.getClient());
    vi.mocked(httpMock.get).mockResolvedValue({
      data: {
        download_url: 'https://s3.example.com/presigned',
        expires_in: 3600,
        filename: 'data.csv',
        content_sha256: ABC_SHA256,
      },
    } as never);

    const fakeS3Fetch = async () => new Blob([new TextEncoder().encode('abc')]);
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    const result = await triggerVerifiedDownload('file-1', { s3Fetch: fakeS3Fetch });

    expect(result.status).toBe('matched');
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalled();
    // Object URL is revoked AFTER the click to free memory.
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:fake-object-url');
  });

  it('rethrows ChecksumMismatchError without producing an object URL', async () => {
    const httpMock = vi.mocked(apiClient.getClient());
    vi.mocked(httpMock.get).mockResolvedValue({
      data: {
        download_url: 'https://s3.example.com/presigned',
        expires_in: 3600,
        filename: 'data.csv',
        content_sha256: ABC_SHA256,
      },
    } as never);
    vi.mocked(httpMock.post).mockResolvedValue({ data: { recorded: true } } as never);
    const fakeS3Fetch = async () => new Blob([new TextEncoder().encode('abd')]);

    await expect(
      triggerVerifiedDownload('file-x', { s3Fetch: fakeS3Fetch })
    ).rejects.toBeInstanceOf(ChecksumMismatchError);
    expect(createObjectURLMock).not.toHaveBeenCalled();
  });
});
