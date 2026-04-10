/**
 * Phase 213.I.7(e) — authStore hydration helper tests.
 *
 * Validates that getInitialUser(), getInitialIsAuthenticated(), and
 * getInitialIsLoading() behave correctly across all four combinations
 * of localStorage state (user ± refresh_token).
 *
 * No network: localStorage is stubbed via vi.stubGlobal.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getInitialIsAuthenticated,
  getInitialIsLoading,
  getInitialUser,
} from '../authStore';

const FAKE_USER = JSON.stringify({
  id: '1',
  email: 'de@example.com',
  name: 'Data Engineer',
  tenant_id: 't1',
  roles: ['DATA_ENGINEER'],
});

describe('getInitialUser()', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('returns parsed User when localStorage has valid user JSON', () => {
    localStorage.setItem('user', FAKE_USER);
    const user = getInitialUser();
    expect(user).not.toBeNull();
    expect(user!.email).toBe('de@example.com');
    expect(user!.roles).toEqual(['DATA_ENGINEER']);
  });

  it('returns null when localStorage has no user', () => {
    expect(getInitialUser()).toBeNull();
  });

  it('returns null when user JSON is malformed', () => {
    localStorage.setItem('user', '{bad json');
    expect(getInitialUser()).toBeNull();
  });
});

describe('getInitialIsAuthenticated()', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('returns true when both user AND refresh_token exist', () => {
    localStorage.setItem('user', FAKE_USER);
    localStorage.setItem('refresh_token', 'tok123');
    expect(getInitialIsAuthenticated()).toBe(true);
  });

  it('returns false when only user exists (no refresh_token)', () => {
    localStorage.setItem('user', FAKE_USER);
    expect(getInitialIsAuthenticated()).toBe(false);
  });

  it('returns false when only refresh_token exists (no user)', () => {
    localStorage.setItem('refresh_token', 'tok123');
    expect(getInitialIsAuthenticated()).toBe(false);
  });

  it('returns false when localStorage is empty', () => {
    expect(getInitialIsAuthenticated()).toBe(false);
  });
});

describe('getInitialIsLoading()', () => {
  it('returns false unconditionally', () => {
    expect(getInitialIsLoading()).toBe(false);
  });

  it('returns false even when user exists in localStorage', () => {
    localStorage.setItem('user', FAKE_USER);
    expect(getInitialIsLoading()).toBe(false);
    localStorage.clear();
  });

  it('returns false even when both user and refresh_token exist', () => {
    localStorage.setItem('user', FAKE_USER);
    localStorage.setItem('refresh_token', 'tok123');
    expect(getInitialIsLoading()).toBe(false);
    localStorage.clear();
  });
});
