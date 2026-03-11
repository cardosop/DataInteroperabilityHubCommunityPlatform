/**
 * Design System Tokens Tests
 * Meshant palette: primary #0A1F44, secondary #2F6BFF, accent #17C6E6
 * Reference: MESHANT_DESIGN_SYSTEM_PLAN.md, tasks.md 28.7.2
 */

import { describe, expect, it } from 'vitest';
import { breakpoints, colors, spacing, typography } from '../tokens';

const SCALE_KEYS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900] as const;
const HEX_REGEX = /^#[0-9A-Fa-f]{6}$/;

describe('Meshant palette in tokens.ts', () => {
  it('primary.500 is Meshant navy (#0A1F44)', () => {
    expect(colors.primary[500]).toBe('#0A1F44');
  });

  it('primary.800 is Meshant navy (#0A1F44) for text on light bg', () => {
    expect(colors.primary[800]).toBe('#0A1F44');
  });

  it('primary.50 is #E8ECF4 for nav active bg', () => {
    expect(colors.primary[50]).toBe('#E8ECF4');
  });

  it('secondary.500 is Meshant blue (#2F6BFF)', () => {
    expect(colors.secondary[500]).toBe('#2F6BFF');
  });

  it('accent.500 is Meshant cyan (#17C6E6)', () => {
    expect(colors.accent[500]).toBe('#17C6E6');
  });

  it('accent.50 exists for light accent backgrounds', () => {
    expect(colors.accent[50]).toBeDefined();
    expect(typeof colors.accent[50]).toBe('string');
    expect(colors.accent[50]).toMatch(HEX_REGEX);
  });

  it('primary, secondary, accent have full scale (50-900) with valid hex values', () => {
    for (const scale of ['primary', 'secondary', 'accent'] as const) {
      const palette = colors[scale];
      for (const key of SCALE_KEYS) {
        expect(palette[key]).toBeDefined();
        expect(palette[key]).toMatch(HEX_REGEX);
      }
    }
  });

  it('tokens.ts primary values align with index.css Meshant palette', () => {
    expect(colors.primary[50]).toBe('#E8ECF4');
    expect(colors.primary[500]).toBe('#0A1F44');
    expect(colors.primary[800]).toBe('#0A1F44');
  });

  it('tokens.ts accent values align with index.css', () => {
    expect(colors.accent[50]).toBe('#E6FAFC');
    expect(colors.accent[500]).toBe('#17C6E6');
    expect(colors.accent[600]).toBe('#12A0C0');
    expect(colors.accent[900]).toBe('#052E3D');
  });
});

describe('Meshant typography tokens', () => {
  it('typography.fontFamily.sans includes Inter', () => {
    expect(typography.fontFamily.sans).toContain('Inter');
  });
});

describe('Meshant spacing tokens', () => {
  it('spacing base (xs) is 4px', () => {
    expect(spacing.xs).toBe('4px');
  });
});

describe('Meshant breakpoints', () => {
  it('breakpoints.lg is 1200px', () => {
    expect(breakpoints.lg).toBe('1200px');
  });
});
