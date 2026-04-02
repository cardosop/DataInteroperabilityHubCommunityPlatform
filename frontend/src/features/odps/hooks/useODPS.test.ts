/**
 * useODPS tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useODPS';

describe('useODPS', () => {
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

  it('exports useODPSWorkflowStatus', () => {
    expect(hookModule.useODPSWorkflowStatus).toBeDefined();
    expect(typeof hookModule.useODPSWorkflowStatus).toBe('function');
  });

  it('exports useCreateODPSProduct', () => {
    expect(hookModule.useCreateODPSProduct).toBeDefined();
    expect(typeof hookModule.useCreateODPSProduct).toBe('function');
  });

  it('exports useLinkODPS', () => {
    expect(hookModule.useLinkODPS).toBeDefined();
    expect(typeof hookModule.useLinkODPS).toBe('function');
  });

  it('exports useUnlinkODPS', () => {
    expect(hookModule.useUnlinkODPS).toBeDefined();
    expect(typeof hookModule.useUnlinkODPS).toBe('function');
  });

  it('exports useODPSLinks', () => {
    expect(hookModule.useODPSLinks).toBeDefined();
    expect(typeof hookModule.useODPSLinks).toBe('function');
  });

});
