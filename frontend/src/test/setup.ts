/**
 * Test Setup
 * Configures testing environment
 */

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Ensure localStorage is available with getItem/setItem. In Vitest/Node 22+, reading
// `globalThis.localStorage` can trigger Node's experimental webstorage and emit
// "--localstorage-file was provided without a valid path"; avoid touching the native
// accessor in test mode and install a pure in-memory store instead.
const store: Record<string, string> = {};
const localStore = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => {
    store[key] = value;
  },
  removeItem: (key: string) => {
    delete store[key];
  },
  clear: () => {
    for (const k of Object.keys(store)) delete store[k];
  },
  get length() {
    return Object.keys(store).length;
  },
  key: (i: number) => Object.keys(store)[i] ?? null,
};

const ensureLocalStorage = () => {
  if (import.meta.env.MODE === 'test') {
    Object.defineProperty(globalThis, 'localStorage', {
      value: localStore,
      writable: true,
      configurable: true,
    });
    if (typeof globalThis.window !== 'undefined') {
      Object.defineProperty(globalThis.window, 'localStorage', {
        value: localStore,
        writable: true,
        configurable: true,
      });
    }
    return;
  }

  try {
    if (
      typeof globalThis.localStorage === 'undefined' ||
      typeof globalThis.localStorage.getItem !== 'function'
    ) {
      Object.defineProperty(globalThis, 'localStorage', { value: localStore, writable: true });
    }
  } catch {
    Object.defineProperty(globalThis, 'localStorage', { value: localStore, writable: true });
  }
  if (typeof globalThis.window !== 'undefined') {
    try {
      const w = globalThis.window as Window & typeof globalThis;
      if (typeof w.localStorage === 'undefined' || typeof w.localStorage?.getItem !== 'function') {
        Object.defineProperty(globalThis.window, 'localStorage', {
          value: localStore,
          writable: true,
        });
      }
    } catch {
      Object.defineProperty(globalThis.window, 'localStorage', {
        value: localStore,
        writable: true,
      });
    }
  }
};
ensureLocalStorage();

// jsdom lacks ResizeObserver; several UI libraries construct one on mount.
// Stub it globally (observe/unobserve/disconnect are no-ops — the observer
// never fires in jsdom anyway). Suites that need real observation override
// this in their own files (e.g. GraphCanvas.test.tsx).
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
}

// jsdom lacks Element.scrollIntoView; palette/sidebar focus helpers call it.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Realm alignment for data-router navigation (react-router 7 + jsdom).
// react-router's createClientSideRequest builds
// `new Request(url, { signal })` on EVERY navigation. The only Request in
// the vitest environment is Node/undici's, which validates the signal with
// instanceof against ITS OWN realm's AbortSignal — a signal minted in this
// jsdom vm context always fails the check ("RequestInit: Expected signal to
// be an instance of AbortSignal") and every createMemoryRouter navigation
// rejects. The signal is react-router's own cancellation handle (never read
// back off the returned Request — it keeps the controller itself), so a
// window.Request that delegates to the native implementation minus the
// signal restores same-realm construction with identical behavior.
if (typeof window !== 'undefined') {
  const NativeRequest = globalThis.Request;
  if (typeof NativeRequest === 'function') {
    Object.defineProperty(window, 'Request', {
      value: class Request extends NativeRequest {
        constructor(input: RequestInfo | URL, init?: RequestInit) {
          const { signal: _signal, ...rest } = init ?? {};
          super(input, rest);
        }
      },
      writable: true,
      configurable: true,
    });
  }
}

// Cleanup after each test
afterEach(() => {
  cleanup();
});
