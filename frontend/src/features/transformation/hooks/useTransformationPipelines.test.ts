/**
 * useTransformationPipelines tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useTransformationPipelines';

describe('useTransformationPipelines', () => {
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

  it('exports useTransformationPipelines', () => {
    expect(hookModule.useTransformationPipelines).toBeDefined();
    expect(typeof hookModule.useTransformationPipelines).toBe('function');
  });

  it('exports useTransformationPipeline', () => {
    expect(hookModule.useTransformationPipeline).toBeDefined();
    expect(typeof hookModule.useTransformationPipeline).toBe('function');
  });

});
