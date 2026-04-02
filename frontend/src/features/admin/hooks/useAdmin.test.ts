/**
 * useAdmin tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useAdmin';

describe('useAdmin', () => {
  it('exports hook functions', () => {
    const exports = Object.keys(hookModule);
    expect(exports.length).toBeGreaterThan(0);
    // All exports should be functions (hooks)
    for (const key of exports) {
      expect(typeof hookModule[key as keyof typeof hookModule]).toBe('function');
    }
  });

  it('all exported hooks follow use* naming convention', () => {
    const exports = Object.keys(hookModule);
    for (const key of exports) {
      if (typeof hookModule[key as keyof typeof hookModule] === 'function') {
        expect(key).toMatch(/^use[A-Z]/);
      }
    }
  });

  it('exports useTenants', () => {
    expect(hookModule.useTenants).toBeDefined();
    expect(typeof hookModule.useTenants).toBe('function');
  });

  it('exports useTenant', () => {
    expect(hookModule.useTenant).toBeDefined();
    expect(typeof hookModule.useTenant).toBe('function');
  });

  it('exports useTenantConfig', () => {
    expect(hookModule.useTenantConfig).toBeDefined();
    expect(typeof hookModule.useTenantConfig).toBe('function');
  });

  it('exports useUsers', () => {
    expect(hookModule.useUsers).toBeDefined();
    expect(typeof hookModule.useUsers).toBe('function');
  });

  it('exports useUser', () => {
    expect(hookModule.useUser).toBeDefined();
    expect(typeof hookModule.useUser).toBe('function');
  });

});
