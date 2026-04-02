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

// Cleanup after each test
afterEach(() => {
  cleanup();
});
