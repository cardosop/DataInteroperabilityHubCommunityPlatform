/**
 * Shadow and Elevation Design Tokens
 *
 * Material Design elevation system with consistent shadow values.
 * Shadows create depth and hierarchy in the UI.
 */

export const shadows = {
  // Elevation levels
  elevation0: 'none', // Flat surfaces
  elevation1: '0px 1px 3px rgba(0, 0, 0, 0.12), 0px 1px 2px rgba(0, 0, 0, 0.24)', // Cards, buttons
  elevation2: '0px 2px 6px rgba(0, 0, 0, 0.12), 0px 2px 4px rgba(0, 0, 0, 0.24)', // Hover states
  elevation4: '0px 4px 12px rgba(0, 0, 0, 0.15), 0px 4px 8px rgba(0, 0, 0, 0.15)', // Modals, dropdowns
  elevation8: '0px 8px 24px rgba(0, 0, 0, 0.15), 0px 8px 16px rgba(0, 0, 0, 0.15)', // Popovers, tooltips
  elevation16: '0px 16px 48px rgba(0, 0, 0, 0.2), 0px 16px 32px rgba(0, 0, 0, 0.2)', // Dialogs

  // Semantic shadow names
  sm: '0px 1px 3px rgba(0, 0, 0, 0.12), 0px 1px 2px rgba(0, 0, 0, 0.24)',
  md: '0px 2px 6px rgba(0, 0, 0, 0.12), 0px 2px 4px rgba(0, 0, 0, 0.24)',
  lg: '0px 4px 12px rgba(0, 0, 0, 0.15), 0px 4px 8px rgba(0, 0, 0, 0.15)',
  xl: '0px 8px 24px rgba(0, 0, 0, 0.15), 0px 8px 16px rgba(0, 0, 0, 0.15)',
  '2xl': '0px 16px 48px rgba(0, 0, 0, 0.2), 0px 16px 32px rgba(0, 0, 0, 0.2)',
} as const;

/**
 * Type-safe shadow token access
 */
export type ShadowToken = typeof shadows;
export type ShadowKey = keyof typeof shadows;

