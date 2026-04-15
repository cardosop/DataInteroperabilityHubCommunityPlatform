/**
 * useTheme — Phase 224.4 tests.
 *
 * Verifies semantics with a real DOM and real localStorage:
 *   - reads persisted preference on mount
 *   - falls back to `prefers-color-scheme: dark` when no preference is set
 *   - reflects the active theme on `<html data-theme>` immediately
 *   - toggling writes to localStorage and flips the DOM attribute
 *   - setTheme accepts explicit 'light' / 'dark' values
 *   - `system` follows media-query changes dynamically
 */

import { renderHook, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTheme, THEME_STORAGE_KEY } from './useTheme';

type MQListener = (ev: { matches: boolean }) => void;

/**
 * Install a controllable `matchMedia` shim. Returns a setter that emits a
 * change event to every subscribed listener — exactly what the browser would
 * do when the OS theme flips.
 */
function installMatchMedia(initialDark: boolean) {
  const listeners: MQListener[] = [];
  const mq = {
    matches: initialDark,
    addEventListener: (_: 'change', cb: MQListener) => listeners.push(cb),
    removeEventListener: (_: 'change', cb: MQListener) => {
      const i = listeners.indexOf(cb);
      if (i >= 0) listeners.splice(i, 1);
    },
    // Legacy Safari API; hooks may fall back to these.
    addListener: (cb: MQListener) => listeners.push(cb),
    removeListener: (cb: MQListener) => {
      const i = listeners.indexOf(cb);
      if (i >= 0) listeners.splice(i, 1);
    },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    dispatchEvent: () => false,
  };
  const matchMediaMock = vi.fn(() => mq);
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: matchMediaMock,
  });
  return {
    emit(dark: boolean) {
      mq.matches = dark;
      for (const cb of [...listeners]) cb({ matches: dark });
    },
  };
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('defaults to system=light when no preference and system is light', () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    // Stored preference is 'system' (nothing persisted), and it resolves to
    // light because the OS media query is light.
    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('defaults to dark when no preference and system prefers dark', () => {
    installMatchMedia(true);
    const { result } = renderHook(() => useTheme());
    // No explicit preference stored → system mode
    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('reads an explicit stored preference on mount', () => {
    installMatchMedia(false);
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
    expect(result.current.resolvedTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('setTheme("dark") persists to localStorage and flips the html attribute', () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('dark'));
    expect(result.current.theme).toBe('dark');
    expect(result.current.resolvedTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('toggleTheme flips light ↔ dark', () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolvedTheme).toBe('light');
    act(() => result.current.toggleTheme());
    expect(result.current.resolvedTheme).toBe('dark');
    act(() => result.current.toggleTheme());
    expect(result.current.resolvedTheme).toBe('light');
  });

  it('setTheme("system") clears the stored preference and follows OS changes', () => {
    const media = installMatchMedia(false);
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('system'));
    expect(result.current.theme).toBe('system');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(result.current.resolvedTheme).toBe('light');
    act(() => media.emit(true));
    expect(result.current.resolvedTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('explicit preference does NOT change when system theme flips', () => {
    const media = installMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('light'));
    act(() => media.emit(true));
    // User said "light" — OS change must be ignored.
    expect(result.current.resolvedTheme).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('index.html inline boot script uses the same storage key + media query as the hook', async () => {
    // Regression guard: the inline script in index.html must stay in lockstep
    // with this hook, otherwise the first-paint theme diverges from React
    // state and users see a flash of light theme (FOUC).
    const fs = await import('fs');
    const path = await import('path');
    // Resolve relative to this test file — use import.meta.url so the test is
    // portable across run-from-repo-root vs. run-from-frontend scenarios.
    const here = new URL(import.meta.url).pathname;
    const indexHtml = path.resolve(here, '../../../../index.html');
    const html = fs.readFileSync(indexHtml, 'utf8');
    expect(html).toContain(THEME_STORAGE_KEY);
    expect(html).toContain('(prefers-color-scheme: dark)');
    expect(html).toMatch(/setAttribute\(\s*['"]data-theme['"]/);
  });

  it('multiple hook instances stay in sync via storage event', () => {
    installMatchMedia(false);
    const a = renderHook(() => useTheme());
    const b = renderHook(() => useTheme());
    act(() => a.result.current.setTheme('dark'));
    // Fire a storage event as another tab would, so the second instance picks
    // up the new preference without a reload.
    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: THEME_STORAGE_KEY,
          newValue: 'dark',
        }),
      );
    });
    expect(b.result.current.resolvedTheme).toBe('dark');
  });
});
