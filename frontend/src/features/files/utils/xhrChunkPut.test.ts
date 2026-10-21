/**
 * xhrChunkPut tests — Phase 260.3.F GAP-D regression suite.
 *
 * The production chunk PUT transport reads ``xhr.getResponseHeader('ETag')``
 * — a browser-only API. The full upload pipeline depends on this
 * header being readable across the CORS boundary; if the S3 bucket
 * isn't configured with ``Access-Control-Expose-Headers: ETag``, the
 * browser returns ``null`` and the multipart flow silently breaks.
 *
 * These tests pin the contract:
 *   - 200 + ETag header → resolved with the captured ETag
 *   - 200 WITHOUT ETag header → rejected with the diagnostic so the
 *     CORS misconfiguration is loud rather than silent
 *   - 5xx → rejected with status + body in the message
 *   - network error → rejected
 *   - abort → rejected
 *
 * Implementation: a minimal stub of ``XMLHttpRequest`` (we own its
 * lifecycle in jsdom; ``vi.stubGlobal`` swaps the constructor in
 * place). No production code is mocked — we exercise the real
 * ``xhrChunkPut`` against a deterministic XHR stub.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { xhrChunkPut } from './multipartUploader';

interface FakeXhrEvent { lengthComputable?: boolean; loaded?: number; total?: number }

class FakeXhr {
  status = 0;
  responseText = '';
  responseHeaders: Record<string, string> = {};
  upload = {
    listeners: new Map<string, (event: FakeXhrEvent) => void>(),
    addEventListener(name: string, fn: (event: FakeXhrEvent) => void) {
      this.listeners.set(name, fn);
    },
  };
  listeners = new Map<string, () => void>();
  timeout = 0;

  open(_method: string, _url: string) {
    void _method;
    void _url;
  }
  setRequestHeader(_name: string, _value: string) {
    void _name;
    void _value;
  }
  addEventListener(name: string, fn: () => void) {
    this.listeners.set(name, fn);
  }
  getResponseHeader(name: string): string | null {
    const lower = name.toLowerCase();
    for (const [k, v] of Object.entries(this.responseHeaders)) {
      if (k.toLowerCase() === lower) return v;
    }
    return null;
  }
  send(_body: BodyInit) {
    void _body;
  }

  // Test helpers — drive lifecycle deterministically.
  fireLoad(status: number, etag?: string, responseText = '') {
    this.status = status;
    this.responseText = responseText;
    if (etag !== undefined) this.responseHeaders['ETag'] = etag;
    this.listeners.get('load')?.();
  }
  fireError() {
    this.listeners.get('error')?.();
  }
  fireAbort() {
    this.listeners.get('abort')?.();
  }
  fireUploadProgress(loaded: number, total: number) {
    this.upload.listeners.get('progress')?.({ lengthComputable: true, loaded, total });
  }
}

let lastXhr: FakeXhr | null = null;

beforeEach(() => {
  lastXhr = null;
  vi.stubGlobal(
    'XMLHttpRequest',
    function FakeCtor(this: FakeXhr) {
      const instance = new FakeXhr();
      lastXhr = instance;
      return instance;
    } as unknown as typeof XMLHttpRequest
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('xhrChunkPut', () => {
  it('resolves with the ETag when the server exposes the header', async () => {
    const blob = new Blob([new Uint8Array(8)], { type: 'application/octet-stream' });
    const promise = xhrChunkPut('https://s3.example.com/upload', blob);

    expect(lastXhr).not.toBeNull();
    lastXhr!.fireLoad(200, '"abc-123"');

    const result = await promise;
    expect(result.etag).toBe('"abc-123"');
  });

  it('reads the ETag header case-insensitively', async () => {
    const blob = new Blob([new Uint8Array(4)]);
    const promise = xhrChunkPut('https://s3.example.com/x', blob);
    // S3 sometimes returns lowercase; getResponseHeader must still find it.
    lastXhr!.responseHeaders = { etag: '"lower-case"' };
    lastXhr!.status = 200;
    lastXhr!.listeners.get('load')?.();
    await expect(promise).resolves.toEqual({ etag: '"lower-case"' });
  });

  it('rejects with a CORS diagnostic when the ETag header is hidden by the browser', async () => {
    // This is the exact symptom of S3 CORS missing
    // ``Access-Control-Expose-Headers: ETag`` — the request succeeds
    // but the browser blocks the header. The error message MUST be
    // diagnostic, not "Upload failed".
    const blob = new Blob([new Uint8Array(4)]);
    const promise = xhrChunkPut('https://s3.example.com/x', blob);
    lastXhr!.fireLoad(200 /* no etag */);
    await expect(promise).rejects.toThrow(/did not expose an ETag header/i);
  });

  it('rejects with status + body on a 5xx', async () => {
    const blob = new Blob([new Uint8Array(4)]);
    const promise = xhrChunkPut('https://s3.example.com/x', blob);
    lastXhr!.fireLoad(500, undefined, '<Error><Code>Internal</Code></Error>');
    await expect(promise).rejects.toThrow(/status 500/);
  });

  it('rejects on a network error', async () => {
    const blob = new Blob([new Uint8Array(4)]);
    const promise = xhrChunkPut('https://s3.example.com/x', blob);
    lastXhr!.fireError();
    await expect(promise).rejects.toThrow(/network error/i);
  });

  it('rejects on abort', async () => {
    const blob = new Blob([new Uint8Array(4)]);
    const promise = xhrChunkPut('https://s3.example.com/x', blob);
    lastXhr!.fireAbort();
    await expect(promise).rejects.toThrow(/aborted/i);
  });

  it('forwards upload progress events to the caller', async () => {
    const blob = new Blob([new Uint8Array(8)]);
    const seen: Array<{ loaded: number; total: number }> = [];
    const promise = xhrChunkPut('https://s3.example.com/x', blob, {
      onProgress: (loaded, total) => seen.push({ loaded, total }),
    });
    lastXhr!.fireUploadProgress(2, 8);
    lastXhr!.fireUploadProgress(8, 8);
    lastXhr!.fireLoad(200, '"x"');
    await promise;
    expect(seen).toEqual([
      { loaded: 2, total: 8 },
      { loaded: 8, total: 8 },
    ]);
  });
});
