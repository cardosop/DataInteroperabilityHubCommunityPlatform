/**
 * Test Setup
 * Configures testing environment
 */

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Ensure localStorage is available and has getItem/setItem (jsdom may provide a partial or missing impl)
const ensureLocalStorage = () => {
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
  if (
    typeof globalThis.localStorage === 'undefined' ||
    typeof globalThis.localStorage.getItem !== 'function'
  ) {
    Object.defineProperty(globalThis, 'localStorage', { value: localStore, writable: true });
  }
  if (
    typeof globalThis.window !== 'undefined' &&
    (typeof (globalThis.window as Window & typeof globalThis).localStorage === 'undefined' ||
      typeof (globalThis.window as Window & typeof globalThis).localStorage?.getItem !== 'function')
  ) {
    Object.defineProperty(globalThis.window, 'localStorage', {
      value: localStore,
      writable: true,
    });
  }
};
ensureLocalStorage();

// Cleanup after each test
afterEach(() => {
  cleanup();
});
