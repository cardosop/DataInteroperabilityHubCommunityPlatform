/**
 * W5.3 (oss-release-remediation R2-F4) — access-token change pins.
 *
 * The unified refresh surface makes the apiClient the SINGLE owner of
 * the access token lifecycle (login, single-flight refresh, cross-tab
 * adoption, logout). Consumers that cache the token — the W5.4
 * WebSocket client's reconnect credential — subscribe via
 * `onAccessTokenChange` instead of guessing where the token changes.
 *
 * The pins drive the REAL client (module singleton): real writes, real
 * listeners, real unsubscribe. No fetch involved — pure API pins.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { apiClient } from './client';

describe('apiClient.onAccessTokenChange (W5.3)', () => {
  beforeEach(() => {
    apiClient.clearTokens();
  });

  afterEach(() => {
    apiClient.clearTokens();
  });

  it('fires with the new token when setAccessToken writes a DIFFERENT value', () => {
    const seen: Array<string | null> = [];
    const unsubscribe = apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.setAccessToken('tok-1');
    apiClient.setAccessToken('tok-2');
    expect(seen).toEqual(['tok-1', 'tok-2']);
    unsubscribe();
  });

  it('does NOT fire when the token value is unchanged (change-only)', () => {
    const seen: Array<string | null> = [];
    apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.setAccessToken('tok-1');
    apiClient.setAccessToken('tok-1'); // same value — not a change
    expect(seen).toEqual(['tok-1']);
  });

  it('fires null when clearTokens drops an existing token', () => {
    const seen: Array<string | null> = [];
    apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.setAccessToken('tok-1');
    apiClient.clearTokens();
    expect(seen).toEqual(['tok-1', null]);
  });

  it('does NOT fire null when clearTokens had nothing to clear', () => {
    const seen: Array<string | null> = [];
    apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.clearTokens();
    expect(seen).toEqual([]);
  });

  it('the returned unsubscribe stops delivery', () => {
    const seen: Array<string | null> = [];
    const unsubscribe = apiClient.onAccessTokenChange((token) => seen.push(token));

    apiClient.setAccessToken('tok-1');
    unsubscribe();
    apiClient.setAccessToken('tok-2');
    expect(seen).toEqual(['tok-1']);
  });

  it('a throwing listener never breaks the token write', () => {
    apiClient.onAccessTokenChange(() => {
      throw new Error('listener bug');
    });
    const good: Array<string | null> = [];
    apiClient.onAccessTokenChange((token) => good.push(token));

    apiClient.setAccessToken('tok-1');
    expect(apiClient.getAccessToken()).toBe('tok-1');
    expect(good).toEqual(['tok-1']);
  });
});
