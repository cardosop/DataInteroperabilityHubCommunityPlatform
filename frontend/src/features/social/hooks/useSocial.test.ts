/**
 * useSocial tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useSocial';

describe('useSocial', () => {
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

  it('exports useRatings', () => {
    expect(hookModule.useRatings).toBeDefined();
    expect(typeof hookModule.useRatings).toBe('function');
  });

  it('exports useSubmitRating', () => {
    expect(hookModule.useSubmitRating).toBeDefined();
    expect(typeof hookModule.useSubmitRating).toBe('function');
  });

  it('exports useReviews', () => {
    expect(hookModule.useReviews).toBeDefined();
    expect(typeof hookModule.useReviews).toBe('function');
  });

  it('exports useReview', () => {
    expect(hookModule.useReview).toBeDefined();
    expect(typeof hookModule.useReview).toBe('function');
  });

  it('exports useSubmitReview', () => {
    expect(hookModule.useSubmitReview).toBeDefined();
    expect(typeof hookModule.useSubmitReview).toBe('function');
  });

});
