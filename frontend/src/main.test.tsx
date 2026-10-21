/**
 * Unit tests for main.tsx — Sentry initialization (task 56.2 / Phase 56 / B3)
 *
 * Phase 94 moved the unhandledrejection listener from main.tsx module-level
 * into App.tsx useEffect (with cleanup). Tests for that handler are now in
 * App.test.tsx. This file tests Sentry.init behaviour only.
 *
 * Isolation strategy
 * ------------------
 * main.tsx has module-level side effects (Sentry.init, createRoot).
 * Each test uses vi.resetModules() + vi.doMock() + dynamic import() so that the
 * module is freshly evaluated with fresh mock references.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

async function importMainWithDsn(dsn: string) {
  vi.stubEnv('VITE_SENTRY_DSN', dsn);

  const init = vi.fn();
  const captureException = vi.fn();

  vi.doMock('@sentry/react', () => ({
    init,
    browserTracingIntegration: vi.fn(() => ({})),
    captureException,
  }));
  vi.doMock('react-dom/client', () => ({
    createRoot: vi.fn(() => ({ render: vi.fn() })),
  }));
  vi.doMock('./App.tsx', () => ({ default: () => null }));
  vi.doMock('./index.css', () => ({}));
  vi.doMock('./shared/styles/a11y.css', () => ({}));
  vi.doMock('@xyflow/react/dist/style.css', () => ({}));

  await import('./main');

  return { init, captureException };
}

describe('main.tsx — Sentry initialization (task 56.2)', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('calls Sentry.init when VITE_SENTRY_DSN is set', async () => {
    const { init } = await importMainWithDsn('https://abc@sentry.io/123');

    expect(init).toHaveBeenCalledOnce();
    expect(init).toHaveBeenCalledWith(
      expect.objectContaining({ dsn: 'https://abc@sentry.io/123' }),
    );
  });

  it('does NOT call Sentry.init when VITE_SENTRY_DSN is empty', async () => {
    const { init } = await importMainWithDsn('');

    expect(init).not.toHaveBeenCalled();
  });

  it('does NOT register unhandledrejection listener at module level (moved to App.tsx)', async () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    await importMainWithDsn('https://abc@sentry.io/123');

    const rejectionCalls = addEventListenerSpy.mock.calls.filter(
      ([type]) => type === 'unhandledrejection',
    );
    expect(rejectionCalls).toHaveLength(0);
    addEventListenerSpy.mockRestore();
  });

  it('does NOT call Sentry.captureException when unhandledrejection fires on window (handler is in App.tsx)', async () => {
    const { captureException } = await importMainWithDsn('https://abc@sentry.io/123');

    // Polyfill PromiseRejectionEvent if needed
    if (typeof globalThis.PromiseRejectionEvent === 'undefined') {
      class PromiseRejectionEventPolyfill extends Event {
        readonly promise: Promise<unknown>;
        readonly reason: unknown;
        constructor(type: string, init: { promise: Promise<unknown>; reason: unknown }) {
          super(type, { cancelable: false, bubbles: false });
          this.promise = init.promise;
          this.reason = init.reason;
        }
      }
      Object.assign(globalThis, { PromiseRejectionEvent: PromiseRejectionEventPolyfill });
    }

    const promise = Promise.reject(new Error('test'));
    promise.catch(() => {});
    window.dispatchEvent(
      new PromiseRejectionEvent('unhandledrejection', {
        promise,
        reason: new Error('test'),
      }),
    );

    // main.tsx no longer registers this handler — App.tsx does
    expect(captureException).not.toHaveBeenCalled();
  });
});
