/**
 * Layout Tests
 * Verifies sidebar 240px, content max-width 1200px (Meshant design system)
 * Reference: tasks.md 28.7.4, MESHANT_DESIGN_SYSTEM_PLAN.md
 */

import { describe, expect, it } from 'vitest';
import { breakpoints, layout } from '../tokens';

const CSS_LENGTH_REGEX = /^\d+px$/;

describe('Layout constants (28.7.4)', () => {
  it('sidebar width is 240px', () => {
    expect(layout.sidebarWidth).toBe('240px');
  });

  it('content max-width is 1200px', () => {
    expect(layout.contentMaxWidth).toBe('1200px');
  });

  it('breakpoints.lg aligns with content max-width (1200px)', () => {
    expect(breakpoints.lg).toBe('1200px');
    expect(breakpoints.lg).toBe(layout.contentMaxWidth);
  });

  it('layout values are valid CSS lengths (Npx format)', () => {
    expect(layout.sidebarWidth).toMatch(CSS_LENGTH_REGEX);
    expect(layout.contentMaxWidth).toMatch(CSS_LENGTH_REGEX);
  });
});
