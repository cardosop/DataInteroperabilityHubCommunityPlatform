/**
 * Typography Design Tokens
 *
 * Comprehensive typography system with font families, sizes, weights, and line heights.
 * Based on modular scale (1.25 - Major Third) for consistent hierarchy.
 */

export const typography = {
  // Font Families
  fontFamily: {
    primary: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
    monospace: "'Fira Code', 'JetBrains Mono', 'Courier New', monospace",
  },

  // Font Sizes (in pixels and rem)
  fontSize: {
    h1: {
      px: 32,
      rem: '2rem',
      lineHeight: 1.2,
    },
    h2: {
      px: 24,
      rem: '1.5rem',
      lineHeight: 1.3,
    },
    h3: {
      px: 20,
      rem: '1.25rem',
      lineHeight: 1.4,
    },
    h4: {
      px: 18,
      rem: '1.125rem',
      lineHeight: 1.4,
    },
    h5: {
      px: 16,
      rem: '1rem',
      lineHeight: 1.5,
    },
    h6: {
      px: 14,
      rem: '0.875rem',
      lineHeight: 1.5,
    },
    body1: {
      px: 16,
      rem: '1rem',
      lineHeight: 1.5,
    },
    body2: {
      px: 14,
      rem: '0.875rem',
      lineHeight: 1.5,
    },
    caption: {
      px: 12,
      rem: '0.75rem',
      lineHeight: 1.4,
    },
    overline: {
      px: 10,
      rem: '0.625rem',
      lineHeight: 1.6,
    },
    code: {
      px: 14,
      rem: '0.875rem',
      lineHeight: 1.5,
    },
  },

  // Font Weights
  fontWeight: {
    light: 300,
    regular: 400,
    medium: 500,
    semiBold: 600,
    bold: 700,
  },

  // Letter Spacing
  letterSpacing: {
    tight: '-0.02em',
    normal: '0em',
    wide: '0.02em',
    wider: '0.05em',
  },
} as const;

/**
 * Type-safe typography token access
 */
export type TypographyToken = typeof typography;
export type FontSize = keyof typeof typography.fontSize;
export type FontWeight = keyof typeof typography.fontWeight;
export type LetterSpacing = keyof typeof typography.letterSpacing;

