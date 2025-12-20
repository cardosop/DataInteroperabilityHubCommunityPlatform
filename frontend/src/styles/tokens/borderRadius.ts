/**
 * Border Radius Design Tokens
 *
 * Consistent border radius values for rounded corners.
 */

export const borderRadius = {
  none: 0,
  sm: 2, // 0.125rem - Small elements
  md: 4, // 0.25rem - Default radius
  lg: 8, // 0.5rem - Cards, buttons
  xl: 12, // 0.75rem - Large cards
  '2xl': 16, // 1rem - Extra large elements
  '3xl': 24, // 1.5rem - Very large elements
  full: 9999, // Fully rounded (pills, avatars)
} as const;

/**
 * Border radius in rem units for CSS usage
 */
export const borderRadiusRem = {
  none: '0',
  sm: '0.125rem',
  md: '0.25rem',
  lg: '0.5rem',
  xl: '0.75rem',
  '2xl': '1rem',
  '3xl': '1.5rem',
  full: '9999px',
} as const;

/**
 * Border width tokens
 */
export const borderWidth = {
  none: 0,
  thin: 1, // Default borders
  medium: 2, // Focus states
  thick: 3, // Emphasis
} as const;

/**
 * Type-safe border radius token access
 */
export type BorderRadiusToken = typeof borderRadius;
export type BorderRadiusKey = keyof typeof borderRadius;
export type BorderWidthToken = typeof borderWidth;
export type BorderWidthKey = keyof typeof borderWidth;

