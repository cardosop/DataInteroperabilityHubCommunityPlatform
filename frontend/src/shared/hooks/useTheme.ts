/**
 * useTheme — light/dark theme state backed by localStorage + system preference.
 *
 * Three modes:
 *   - 'light' / 'dark': explicit user choice, written to localStorage.
 *   - 'system':         no stored preference; follows `prefers-color-scheme`.
 *
 * FOUC prevention: the initial `data-theme` is set by a synchronous inline
 * script in `index.html` (see `<!-- Phase 224.4 -->`) that runs **before** CSS
 * parses, using the same storage key + media query as this hook. The hook's
 * `useEffect` below then keeps the attribute in sync with React state for the
 * rest of the session — it does not provide first-paint safety on its own.
 * Any change to `THEME_STORAGE_KEY` or `MEDIA_QUERY` must be mirrored in the
 * HTML script.
 *
 * Cross-tab sync: a `storage` event on `THEME_STORAGE_KEY` re-reads the
 * preference so two open tabs don't drift apart.
 */

import { useCallback, useEffect, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'meshant.theme';
const DATA_ATTR = 'data-theme';
const MEDIA_QUERY = '(prefers-color-scheme: dark)';

function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // Accessing localStorage can throw in sandboxed contexts (private mode,
    // disabled storage, blocked third-party iframes). Fall through to system.
  }
  return 'system';
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia(MEDIA_QUERY).matches;
}

function resolve(pref: ThemePreference, systemDark: boolean): ResolvedTheme {
  if (pref === 'light') return 'light';
  if (pref === 'dark') return 'dark';
  return systemDark ? 'dark' : 'light';
}

function applyToDOM(theme: ResolvedTheme) {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute(DATA_ATTR, theme);
}

export interface UseThemeResult {
  /** Current stored preference (may be 'system'). */
  theme: ThemePreference;
  /** Concrete theme the UI should render right now. */
  resolvedTheme: ResolvedTheme;
  /** Persist an explicit choice (or 'system' to clear the override). */
  setTheme: (next: ThemePreference) => void;
  /** Flip between light and dark; 'system' is treated as its current resolution. */
  toggleTheme: () => void;
}

export function useTheme(): UseThemeResult {
  const [theme, setThemeState] = useState<ThemePreference>(() => readStoredPreference());
  const [systemDark, setSystemDark] = useState<boolean>(() => systemPrefersDark());

  // Apply the current resolution to <html> immediately so CSS picks it up
  // before paint. This runs on mount and any time either input changes.
  useEffect(() => {
    applyToDOM(resolve(theme, systemDark));
  }, [theme, systemDark]);

  // Subscribe to OS-level theme changes.
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }
    const mq = window.matchMedia(MEDIA_QUERY);
    const onChange = (ev: MediaQueryListEvent | { matches: boolean }) => {
      setSystemDark(ev.matches);
    };
    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', onChange);
      return () => mq.removeEventListener('change', onChange);
    }
    // Safari < 14 / jsdom compatibility fallback.
    const legacy = mq as unknown as {
      addListener: (cb: (ev: { matches: boolean }) => void) => void;
      removeListener: (cb: (ev: { matches: boolean }) => void) => void;
    };
    legacy.addListener(onChange);
    return () => legacy.removeListener(onChange);
  }, []);

  // Cross-tab sync: react to another tab changing the preference.
  useEffect(() => {
    const onStorage = (ev: StorageEvent) => {
      if (ev.key !== THEME_STORAGE_KEY) return;
      setThemeState(readStoredPreference());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const setTheme = useCallback((next: ThemePreference) => {
    try {
      if (next === 'system') {
        localStorage.removeItem(THEME_STORAGE_KEY);
      } else {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      }
    } catch {
      // Storage unavailable — still update in-memory state so the current
      // session reflects the user's click.
    }
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const current = resolve(prev, systemDark);
      const next: ThemePreference = current === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // ignore
      }
      return next;
    });
  }, [systemDark]);

  return {
    theme,
    resolvedTheme: resolve(theme, systemDark),
    setTheme,
    toggleTheme,
  };
}
