/**
 * useScheduledIngestion tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useScheduledIngestion';

describe('useScheduledIngestion', () => {
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

  it('exports useScheduledIngestions', () => {
    expect(hookModule.useScheduledIngestions).toBeDefined();
    expect(typeof hookModule.useScheduledIngestions).toBe('function');
  });

  it('exports useScheduledIngestion', () => {
    expect(hookModule.useScheduledIngestion).toBeDefined();
    expect(typeof hookModule.useScheduledIngestion).toBe('function');
  });

  it('exports useScheduledIngestionRuns', () => {
    expect(hookModule.useScheduledIngestionRuns).toBeDefined();
    expect(typeof hookModule.useScheduledIngestionRuns).toBe('function');
  });

  it('exports useCreateScheduledIngestion', () => {
    expect(hookModule.useCreateScheduledIngestion).toBeDefined();
    expect(typeof hookModule.useCreateScheduledIngestion).toBe('function');
  });

  it('exports useUpdateScheduledIngestion', () => {
    expect(hookModule.useUpdateScheduledIngestion).toBeDefined();
    expect(typeof hookModule.useUpdateScheduledIngestion).toBe('function');
  });

});
