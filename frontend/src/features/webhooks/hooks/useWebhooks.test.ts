/**
 * useWebhooks tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useWebhooks';

describe('useWebhooks', () => {
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

  it('exports useWebhooks', () => {
    expect(hookModule.useWebhooks).toBeDefined();
    expect(typeof hookModule.useWebhooks).toBe('function');
  });

  it('exports useWebhook', () => {
    expect(hookModule.useWebhook).toBeDefined();
    expect(typeof hookModule.useWebhook).toBe('function');
  });

  it('exports useWebhookEventTypes', () => {
    expect(hookModule.useWebhookEventTypes).toBeDefined();
    expect(typeof hookModule.useWebhookEventTypes).toBe('function');
  });

  it('exports useCreateWebhook', () => {
    expect(hookModule.useCreateWebhook).toBeDefined();
    expect(typeof hookModule.useCreateWebhook).toBe('function');
  });

  it('exports useUpdateWebhook', () => {
    expect(hookModule.useUpdateWebhook).toBeDefined();
    expect(typeof hookModule.useUpdateWebhook).toBe('function');
  });

});
