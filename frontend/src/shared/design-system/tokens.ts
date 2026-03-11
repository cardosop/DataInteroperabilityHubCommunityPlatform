/**
 * Design System Tokens
 * Meshant palette: primary #0A1F44, secondary #2F6BFF, accent #17C6E6
 * Reference: MESHANT_DESIGN_SYSTEM_PLAN.md, docs/UI/DESIGN_SYSTEM.md
 */

export const colors = {
  primary: {
    50: '#E8ECF4',
    100: '#CFD8E8',
    200: '#9BA8C4',
    300: '#6778A0',
    400: '#33497C',
    500: '#0A1F44',
    600: '#081A3A',
    700: '#061530',
    800: '#0A1F44',
    900: '#030D22',
  },
  secondary: {
    50: '#EBF0FF',
    100: '#D6E0FF',
    200: '#ADBFFF',
    300: '#849EFF',
    400: '#5B7DFF',
    500: '#2F6BFF',
    600: '#2756E6',
    700: '#1F41CC',
    800: '#172DB3',
    900: '#0F1999',
  },
  accent: {
    50: '#E6FAFC',
    100: '#CCF5F9',
    200: '#99EBF3',
    300: '#66E0ED',
    400: '#33D6E7',
    500: '#17C6E6',
    600: '#12A0C0',
    700: '#0E7A9A',
    800: '#095474',
    900: '#052E3D',
  },
  success: {
    50: '#E8F5E9',
    100: '#C8E6C9',
    500: '#4CAF50',
    700: '#388E3C',
    900: '#1B5E20',
  },
  warning: {
    50: '#FFF8E1',
    100: '#FFECB3',
    500: '#FFC107',
    700: '#F57C00',
    900: '#E65100',
  },
  error: {
    50: '#FFEBEE',
    100: '#FFCDD2',
    500: '#F44336',
    700: '#D32F2F',
    900: '#B71C1C',
  },
  neutral: {
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
} as const;

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
  '3xl': '64px',
} as const;

export const typography = {
  fontFamily: {
    sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
    mono: ['Monaco', 'Menlo', 'Consolas', 'monospace'],
  },
  fontSize: {
    xs: '12px',
    sm: '14px',
    base: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px',
    '4xl': '36px',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
  },
} as const;

export const breakpoints = {
  sm: '600px',
  md: '900px',
  lg: '1200px',
  xl: '1536px',
} as const;

/** Layout constants — align with index.css --layout-* variables */
export const layout = {
  sidebarWidth: '240px',
  contentMaxWidth: '1200px',
} as const;

export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
} as const;

export const borderRadius = {
  none: '0',
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px',
} as const;
