import { describe, expect, it } from 'vitest';
import { isPathHiddenInMvpMode } from './mvpNav';

describe('mvpNav', () => {
  it('hides non-MVP paths only when MVP flag is on', () => {
    expect(isPathHiddenInMvpMode('/mesh', false)).toBe(false);
    expect(isPathHiddenInMvpMode('/mesh', true)).toBe(true);
    expect(isPathHiddenInMvpMode('/contracts', true)).toBe(false);
    expect(isPathHiddenInMvpMode('/ai/search', true)).toBe(true);
    expect(isPathHiddenInMvpMode('/scheduled-ingestions', true)).toBe(false);
  });
});
