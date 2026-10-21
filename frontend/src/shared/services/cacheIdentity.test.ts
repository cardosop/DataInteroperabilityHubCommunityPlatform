/**
 * W5.2 — pins for the identity-boundary cache bus (no mocks: the real
 * module registry).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  identityCacheInvalidatorCount,
  invalidateIdentityCaches,
  registerIdentityCacheInvalidator,
} from './cacheIdentity';

describe('cacheIdentity bus', () => {
  beforeEach(() => {
    // Leave the module registry as the production modules registered it;
    // tests only ADD scoped listeners and always unregister.
  });

  it('fires every registered invalidator with the boundary', () => {
    const seen: string[] = [];
    const unregisterA = registerIdentityCacheInvalidator((b) => seen.push(`a:${b}`));
    const unregisterB = registerIdentityCacheInvalidator((b) => seen.push(`b:${b}`));
    try {
      invalidateIdentityCaches('tenant-switch');
      expect(seen.sort()).toEqual(['a:tenant-switch', 'b:tenant-switch']);
    } finally {
      unregisterA();
      unregisterB();
    }
  });

  it('unregister stops delivery', () => {
    const seen: string[] = [];
    const unregister = registerIdentityCacheInvalidator((b) => seen.push(b));
    unregister();
    invalidateIdentityCaches('logout');
    expect(seen).toEqual([]);
  });

  it('registering the same function twice is idempotent', () => {
    let calls = 0;
    const fn = () => {
      calls += 1;
    };
    const a = registerIdentityCacheInvalidator(fn);
    const b = registerIdentityCacheInvalidator(fn);
    try {
      invalidateIdentityCaches('login');
      expect(calls).toBe(1);
    } finally {
      a();
      b();
    }
  });

  it('a throwing invalidator never breaks the boundary', () => {
    const unregisterBad = registerIdentityCacheInvalidator(() => {
      throw new Error('broken invalidator');
    });
    const seen: string[] = [];
    const unregisterGood = registerIdentityCacheInvalidator((b) => seen.push(b));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      invalidateIdentityCaches('logout');
      expect(seen).toEqual(['logout']);
      expect(warn).toHaveBeenCalled();
    } finally {
      unregisterBad();
      unregisterGood();
      warn.mockRestore();
    }
  });

  it('the production modules register their invalidators at import time', async () => {
    // Importing the production wiring (query client + capabilities
    // service) registers their invalidators — the bus is live without
    // any explicit init call (module side effects, once per process).
    const before = identityCacheInvalidatorCount();
    await import('../../app/providers/queryClient');
    await import('../../features/capabilities/services/capabilitiesService');
    expect(identityCacheInvalidatorCount()).toBeGreaterThan(before);
  });
});
