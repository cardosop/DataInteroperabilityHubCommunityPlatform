/**
 * useCompliance tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useCompliance';

describe('useCompliance', () => {
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

  it('exports useComplianceRuns', () => {
    expect(hookModule.useComplianceRuns).toBeDefined();
    expect(typeof hookModule.useComplianceRuns).toBe('function');
  });

  it('exports useComplianceRun', () => {
    expect(hookModule.useComplianceRun).toBeDefined();
    expect(typeof hookModule.useComplianceRun).toBe('function');
  });

  it('exports useComplianceRunResults', () => {
    expect(hookModule.useComplianceRunResults).toBeDefined();
    expect(typeof hookModule.useComplianceRunResults).toBe('function');
  });

  it('exports useCreateComplianceRun', () => {
    expect(hookModule.useCreateComplianceRun).toBeDefined();
    expect(typeof hookModule.useCreateComplianceRun).toBe('function');
  });

  it('exports useCancelComplianceRun', () => {
    expect(hookModule.useCancelComplianceRun).toBeDefined();
    expect(typeof hookModule.useCancelComplianceRun).toBe('function');
  });

});
