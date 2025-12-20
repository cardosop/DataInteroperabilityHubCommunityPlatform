/**
 * Spacing Design Tokens
 *
 * Spacing system based on 4px base unit for consistent layout.
 * All spacing values are multiples of 4px.
 */

export const spacing = {
  // Base unit: 4px
  0: 0,
  1: 4, // 0.25rem
  2: 8, // 0.5rem
  3: 12, // 0.75rem
  4: 16, // 1rem - Default spacing
  5: 20, // 1.25rem
  6: 24, // 1.5rem
  7: 28, // 1.75rem
  8: 32, // 2rem
  9: 36, // 2.25rem
  10: 40, // 2.5rem
  12: 48, // 3rem
  14: 56, // 3.5rem
  16: 64, // 4rem
  20: 80, // 5rem
  24: 96, // 6rem
  32: 128, // 8rem
  40: 160, // 10rem
  48: 192, // 12rem
  64: 256, // 16rem
} as const;

/**
 * Spacing scale in rem units for CSS usage
 */
export const spacingRem = {
  0: '0',
  1: '0.25rem',
  2: '0.5rem',
  3: '0.75rem',
  4: '1rem',
  5: '1.25rem',
  6: '1.5rem',
  7: '1.75rem',
  8: '2rem',
  9: '2.25rem',
  10: '2.5rem',
  12: '3rem',
  14: '3.5rem',
  16: '4rem',
  20: '5rem',
  24: '6rem',
  32: '8rem',
  40: '10rem',
  48: '12rem',
  64: '16rem',
} as const;

/**
 * Semantic spacing names for common use cases
 */
export const spacingSemantic = {
  none: spacing[0],
  xs: spacing[1], // 4px - Tight spacing
  sm: spacing[2], // 8px - Small spacing
  md: spacing[4], // 16px - Default spacing
  lg: spacing[6], // 24px - Large spacing
  xl: spacing[8], // 32px - Extra large spacing
  '2xl': spacing[12], // 48px - Section spacing
  '3xl': spacing[16], // 64px - Page spacing
  '4xl': spacing[24], // 96px - Major section spacing
} as const;

/**
 * Type-safe spacing token access
 */
export type SpacingToken = typeof spacing;
export type SpacingKey = keyof typeof spacing;
export type SpacingSemantic = keyof typeof spacingSemantic;

