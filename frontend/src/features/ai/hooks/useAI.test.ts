/**
 * useAI tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useAI';

describe('useAI', () => {
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

  it('exports useNaturalLanguageSearch', () => {
    expect(hookModule.useNaturalLanguageSearch).toBeDefined();
    expect(typeof hookModule.useNaturalLanguageSearch).toBe('function');
  });

  it('exports useSchemaMatching', () => {
    expect(hookModule.useSchemaMatching).toBeDefined();
    expect(typeof hookModule.useSchemaMatching).toBe('function');
  });

});
