/**
 * Brand constant unit tests (Phase 29.0.4)
 * APP_NAME from VITE_APP_NAME env; default 'Meshant'.
 * No mocks/stubs of import.meta.env.
 * For "when set" case: run with VITE_APP_NAME=CustomBrand npm run test:run
 */
import { describe, expect, it } from 'vitest';
import { APP_NAME } from '../brand';

describe('APP_NAME brand constant', () => {
  it('APP_NAME is a non-empty string', () => {
    expect(typeof APP_NAME).toBe('string');
    expect(APP_NAME.length).toBeGreaterThan(0);
  });

  it('APP_NAME equals VITE_APP_NAME when set, else Meshant (no mocks)', () => {
    const expected = process.env.VITE_APP_NAME ?? 'Meshant';
    expect(APP_NAME).toBe(expected);
  });
});
