/**
 * Phase 277.B.067 — cross-tab auth sync tests (rewritten: the previous
 * suite never mounted the hook — it replicated the hook's logic inline
 * and asserted on spies the tests themselves called, i.e. tautological).
 *
 * These tests MOUNT the hook under a real MemoryRouter and dispatch REAL
 * StorageEvents at the window; the assertions observe the hook's ACTUAL
 * side effects (apiClient token adoption/clearance, auth re-initialization,
 * navigation to /login).
 */
import { render, screen } from '@testing-library/react';
import { act, StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../shared/api/client';
import { authService } from '../services/authService';
import { useCrossTabAuthSync } from './useCrossTabAuthSync';

const ACCESS_TOKEN_KEY = 'access_token';
const SYNC_TS_KEY = '_auth_sync_ts';
const USER_KEY = 'user';

// Sample valid JWT (payload: {"exp":2000000000,"sub":"test"})
const FUTURE_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  btoa(JSON.stringify({ exp: 2000000000, sub: 'test' })) +
  '.signature';

const EXPIRED_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  btoa(JSON.stringify({ exp: 1000000, sub: 'test' })) +
  '.signature';

function PathDisplay(): React.ReactElement {
  useCrossTabAuthSync();
  const location = useLocation();
  return <div data-testid="path">{location.pathname}</div>;
}

function renderHook(): void {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="*" element={<PathDisplay />} />
      </Routes>
    </MemoryRouter>
  );
}

function dispatchStorage(key: string, newValue: string | null): void {
  // NOTE: no `storageArea` init member — jsdom's StorageEventInit
  // conversion rejects it, and the hook never reads it.
  const event = new StorageEvent('storage', { key, newValue, oldValue: null });
  act(() => {
    window.dispatchEvent(event);
  });
}

describe('useCrossTabAuthSync — storage event handling', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('adopts a valid token from another tab (login)', () => {
    const setSpy = vi.spyOn(apiClient, 'setAccessToken');
    const initSpy = vi.spyOn(authService, 'initializeAuth');
    renderHook();

    // 11.1 protocol: the writer REMOVES the token from localStorage in
    // the same tick it wrote it — the value arrives via the event
    // payload (e.newValue), never via a localStorage read.
    dispatchStorage(ACCESS_TOKEN_KEY, FUTURE_JWT);

    expect(setSpy).toHaveBeenCalledWith(FUTURE_JWT);
    expect(initSpy).toHaveBeenCalled();
  });

  it('does not adopt an expired token from another tab', () => {
    const setSpy = vi.spyOn(apiClient, 'setAccessToken');
    const initSpy = vi.spyOn(authService, 'initializeAuth');
    renderHook();

    dispatchStorage(ACCESS_TOKEN_KEY, EXPIRED_JWT);

    expect(setSpy).not.toHaveBeenCalled();
    expect(initSpy).not.toHaveBeenCalled();
  });

  it('ignores a malformed JWT without throwing', () => {
    const setSpy = vi.spyOn(apiClient, 'setAccessToken');
    renderHook();

    expect(() => {
      dispatchStorage(ACCESS_TOKEN_KEY, 'not-a-valid-jwt');
    }).not.toThrow();
    expect(setSpy).not.toHaveBeenCalled();
  });

  it('does NOT log out on an access_token removal (sync-write cleanup)', () => {
    // Regression: the 11.1 sync write removes the token right after
    // writing it — a removal event fires in every sibling tab on every
    // login/rotation. Treating it as logout made tab B bounce to /login
    // immediately after adopting the login.
    const clearSpy = vi.spyOn(apiClient, 'clearTokens');
    renderHook();

    dispatchStorage(ACCESS_TOKEN_KEY, null);

    expect(clearSpy).not.toHaveBeenCalled();
  });

  it('logs out when the user profile is removed in another tab', () => {
    const clearSpy = vi.spyOn(apiClient, 'clearTokens');
    renderHook();

    // clearAuth() removes access_token first, then the user profile —
    // the user-key removal is the reliable "session ended" signal.
    dispatchStorage(USER_KEY, null);

    expect(clearSpy).toHaveBeenCalled();
    expect(screen.getByTestId('path')).toHaveTextContent('/login');
  });

  it('ignores a _auth_sync_ts bump (values ride the access_token event)', () => {
    const setSpy = vi.spyOn(apiClient, 'setAccessToken');
    const clearSpy = vi.spyOn(apiClient, 'clearTokens');
    renderHook();

    localStorage.setItem(ACCESS_TOKEN_KEY, FUTURE_JWT);
    dispatchStorage(SYNC_TS_KEY, String(Date.now()));

    expect(setSpy).not.toHaveBeenCalled();
    expect(clearSpy).not.toHaveBeenCalled();
  });

  it('does not react to unrelated storage keys', () => {
    const setSpy = vi.spyOn(apiClient, 'setAccessToken');
    const clearSpy = vi.spyOn(apiClient, 'clearTokens');
    renderHook();

    localStorage.setItem(ACCESS_TOKEN_KEY, FUTURE_JWT);
    dispatchStorage('unrelated_key', 'some_value');

    expect(setSpy).not.toHaveBeenCalled();
    expect(clearSpy).not.toHaveBeenCalled();
  });

  it('survives React StrictMode double-mount and keeps the listener attached', () => {
    // Regression: the dedup ref was never reset on cleanup, so in dev
    // StrictMode the second effect pass early-returned and the listener
    // stayed DETACHED — the cross-tab E2E never saw the storage event.
    const clearSpy = vi.spyOn(apiClient, 'clearTokens');
    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="*" element={<PathDisplay />} />
          </Routes>
        </MemoryRouter>
      </StrictMode>
    );

    localStorage.removeItem(USER_KEY);
    dispatchStorage(USER_KEY, null);

    expect(clearSpy).toHaveBeenCalled();
    expect(screen.getByTestId('path')).toHaveTextContent('/login');
  });
});
