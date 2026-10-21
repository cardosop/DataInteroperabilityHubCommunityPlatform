/**
 * useDQ tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useDQ';

describe('useDQ', () => {
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

  it('exports useDQRuns', () => {
    expect(hookModule.useDQRuns).toBeDefined();
    expect(typeof hookModule.useDQRuns).toBe('function');
  });

  it('exports useDQRun', () => {
    expect(hookModule.useDQRun).toBeDefined();
    expect(typeof hookModule.useDQRun).toBe('function');
  });

  it('exports useDQRunResults', () => {
    expect(hookModule.useDQRunResults).toBeDefined();
    expect(typeof hookModule.useDQRunResults).toBe('function');
  });

  it('exports useCreateDQRun', () => {
    expect(hookModule.useCreateDQRun).toBeDefined();
    expect(typeof hookModule.useCreateDQRun).toBe('function');
  });

});
