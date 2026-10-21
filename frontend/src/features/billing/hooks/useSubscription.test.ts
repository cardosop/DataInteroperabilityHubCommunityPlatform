/**
 * useSubscription tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useSubscription';

describe('useSubscription', () => {
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

  it('exports useCurrentSubscription', () => {
    expect(hookModule.useCurrentSubscription).toBeDefined();
    expect(typeof hookModule.useCurrentSubscription).toBe('function');
  });

  it('exports usePlans', () => {
    expect(hookModule.usePlans).toBeDefined();
    expect(typeof hookModule.usePlans).toBe('function');
  });

  it('exports useChangePlan', () => {
    expect(hookModule.useChangePlan).toBeDefined();
    expect(typeof hookModule.useChangePlan).toBe('function');
  });

  it('exports useInvoices', () => {
    expect(hookModule.useInvoices).toBeDefined();
    expect(typeof hookModule.useInvoices).toBe('function');
  });

});
