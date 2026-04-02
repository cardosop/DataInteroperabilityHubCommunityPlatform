/**
 * useFiles tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useFiles';

describe('useFiles', () => {
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

  it('exports useFiles', () => {
    expect(hookModule.useFiles).toBeDefined();
    expect(typeof hookModule.useFiles).toBe('function');
  });

  it('exports useFile', () => {
    expect(hookModule.useFile).toBeDefined();
    expect(typeof hookModule.useFile).toBe('function');
  });

  it('exports useUploadFile', () => {
    expect(hookModule.useUploadFile).toBeDefined();
    expect(typeof hookModule.useUploadFile).toBe('function');
  });

  it('exports useDeleteFile', () => {
    expect(hookModule.useDeleteFile).toBeDefined();
    expect(typeof hookModule.useDeleteFile).toBe('function');
  });

});
