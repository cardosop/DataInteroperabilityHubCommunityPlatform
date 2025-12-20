/**
 * Color Palette Design Tokens
 *
 * Comprehensive color system following Material Design principles.
 * All colors meet WCAG 2.1 AA accessibility standards.
 */

export const colors = {
  // Primary Colors - Blue
  primary: {
    50: '#E3F2FD',
    100: '#BBDEFB',
    200: '#90CAF9',
    300: '#64B5F6',
    400: '#42A5F5',
    500: '#2196F3', // Base primary color
    600: '#1E88E5',
    700: '#1976D2',
    800: '#1565C0',
    900: '#0D47A1',
  },

  // Secondary Colors - Teal
  secondary: {
    50: '#E0F2F1',
    100: '#B2DFDB',
    200: '#80CBC4',
    300: '#4DB6AC',
    400: '#26A69A',
    500: '#009688', // Base secondary color
    600: '#00897B',
    700: '#00796B',
    800: '#00695C',
    900: '#004D40',
  },

  // Success Colors - Green
  success: {
    50: '#E8F5E9',
    100: '#C8E6C9',
    200: '#A5D6A7',
    300: '#81C784',
    400: '#66BB6A',
    500: '#4CAF50', // Base success color
    600: '#43A047',
    700: '#388E3C',
    800: '#2E7D32',
    900: '#1B5E20',
  },

  // Error Colors - Red
  error: {
    50: '#FFEBEE',
    100: '#FFCDD2',
    200: '#EF9A9A',
    300: '#E57373',
    400: '#EF5350',
    500: '#F44336', // Base error color
    600: '#E53935',
    700: '#D32F2F',
    800: '#C62828',
    900: '#B71C1C',
  },

  // Warning Colors - Orange/Amber
  warning: {
    50: '#FFF3E0',
    100: '#FFE0B2',
    200: '#FFCC80',
    300: '#FFB74D',
    400: '#FFA726',
    500: '#FF9800', // Base warning color
    600: '#FB8C00',
    700: '#F57C00',
    800: '#EF6C00',
    900: '#E65100',
  },

  // Info Colors - Cyan/Blue
  info: {
    50: '#E0F7FA',
    100: '#B2EBF2',
    200: '#80DEEA',
    300: '#4DD0E1',
    400: '#26C6DA',
    500: '#00BCD4', // Base info color
    600: '#00ACC1',
    700: '#0097A7',
    800: '#00838F',
    900: '#006064',
  },

  // Neutral/Gray Colors
  gray: {
    50: '#FAFAFA',
    100: '#F5F5F5',
    200: '#EEEEEE',
    300: '#E0E0E0',
    400: '#BDBDBD',
    500: '#9E9E9E',
    600: '#757575',
    700: '#616161',
    800: '#424242',
    900: '#212121',
  },

  // Semantic Color Mappings
  semantic: {
    // Text colors
    textPrimary: '#212121', // gray-900
    textSecondary: '#757575', // gray-600
    textDisabled: '#BDBDBD', // gray-400
    textHint: '#9E9E9E', // gray-500

    // Background colors
    backgroundDefault: '#FFFFFF',
    backgroundPaper: '#FAFAFA', // gray-50
    backgroundElevated: '#FFFFFF',

    // Border colors
    borderDefault: '#E0E0E0', // gray-300
    borderDivider: '#EEEEEE', // gray-200
    borderFocus: '#2196F3', // primary-500
    borderError: '#F44336', // error-500
    borderSuccess: '#4CAF50', // success-500
    borderWarning: '#FF9800', // warning-500

    // Action colors
    actionActive: 'rgba(0, 0, 0, 0.54)',
    actionHover: 'rgba(0, 0, 0, 0.04)',
    actionSelected: 'rgba(0, 0, 0, 0.08)',
    actionDisabled: 'rgba(0, 0, 0, 0.26)',
    actionDisabledBackground: 'rgba(0, 0, 0, 0.12)',
  },
} as const;

/**
 * Type-safe color token access
 */
export type ColorToken = typeof colors;
export type PrimaryColor = keyof typeof colors.primary;
export type SecondaryColor = keyof typeof colors.secondary;
export type SemanticColor = keyof typeof colors.semantic;

