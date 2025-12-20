/**
 * Breakpoint Design Tokens
 *
 * Responsive breakpoints for mobile, tablet, and desktop layouts.
 * Values are in pixels and represent minimum viewport widths.
 */

export const breakpoints = {
  // Mobile (default)
  xs: 0, // Extra small devices (phones)
  sm: 600, // Small devices (large phones, small tablets)

  // Tablet
  md: 900, // Medium devices (tablets)

  // Desktop
  lg: 1200, // Large devices (desktops)
  xl: 1536, // Extra large devices (large desktops)
} as const;

/**
 * Breakpoint values in pixels (for JavaScript/TypeScript usage)
 */
export const breakpointValues = {
  xs: breakpoints.xs,
  sm: breakpoints.sm,
  md: breakpoints.md,
  lg: breakpoints.lg,
  xl: breakpoints.xl,
} as const;

/**
 * Breakpoint media query strings (for CSS usage)
 */
export const breakpointMediaQueries = {
  xs: '(min-width: 0px)',
  sm: '(min-width: 600px)',
  md: '(min-width: 900px)',
  lg: '(min-width: 1200px)',
  xl: '(min-width: 1536px)',
} as const;

/**
 * Semantic breakpoint names
 */
export const breakpointSemantic = {
  mobile: breakpoints.xs,
  tablet: breakpoints.md,
  desktop: breakpoints.lg,
} as const;

/**
 * Type-safe breakpoint token access
 */
export type BreakpointToken = typeof breakpoints;
export type BreakpointKey = keyof typeof breakpoints;
export type BreakpointSemantic = keyof typeof breakpointSemantic;

