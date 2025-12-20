/**
 * Material-UI Theme Configuration
 *
 * MUI theme configuration with custom branding based on design tokens.
 * All colors, typography, and spacing are sourced from design tokens.
 */
import { borderRadius } from '@/styles/tokens/borderRadius'
import { colors } from '@/styles/tokens/colors'
import { spacing } from '@/styles/tokens/spacing'
import { typography } from '@/styles/tokens/typography'
import type { PaletteMode, Theme, ThemeOptions } from '@mui/material/styles'
import { createTheme } from '@mui/material/styles'

/**
 * Create custom MUI theme based on design tokens
 */
export const createAppTheme = (mode: PaletteMode = 'light'): Theme => {
  const isLight = mode === 'light'

  const themeOptions: ThemeOptions = {
    palette: {
      mode,
      // Primary colors from design tokens
      primary: {
        main: colors.primary[500],
        light: colors.primary[300],
        dark: colors.primary[700],
        contrastText: '#FFFFFF',
        ...(isLight && {
          '50': colors.primary[50],
          '100': colors.primary[100],
          '200': colors.primary[200],
          '300': colors.primary[300],
          '400': colors.primary[400],
          '500': colors.primary[500],
          '600': colors.primary[600],
          '700': colors.primary[700],
          '800': colors.primary[800],
          '900': colors.primary[900],
        }),
      },
      // Secondary colors from design tokens
      secondary: {
        main: colors.secondary[500],
        light: colors.secondary[300],
        dark: colors.secondary[700],
        contrastText: '#FFFFFF',
        ...(isLight && {
          '50': colors.secondary[50],
          '100': colors.secondary[100],
          '200': colors.secondary[200],
          '300': colors.secondary[300],
          '400': colors.secondary[400],
          '500': colors.secondary[500],
          '600': colors.secondary[600],
          '700': colors.secondary[700],
          '800': colors.secondary[800],
          '900': colors.secondary[900],
        }),
      },
      // Error colors from design tokens
      error: {
        main: colors.error[500],
        light: colors.error[300],
        dark: colors.error[700],
        contrastText: '#FFFFFF',
      },
      // Warning colors from design tokens
      warning: {
        main: colors.warning[500],
        light: colors.warning[300],
        dark: colors.warning[700],
        contrastText: '#FFFFFF',
      },
      // Info colors from design tokens
      info: {
        main: colors.info[500],
        light: colors.info[300],
        dark: colors.info[700],
        contrastText: '#FFFFFF',
      },
      // Success colors from design tokens
      success: {
        main: colors.success[500],
        light: colors.success[300],
        dark: colors.success[700],
        contrastText: '#FFFFFF',
      },
      // Background colors from semantic tokens
      background: {
        default: isLight ? colors.semantic.backgroundDefault : '#121212',
        paper: isLight ? colors.semantic.backgroundPaper : '#1E1E1E',
      },
      // Text colors from semantic tokens
      text: {
        primary: isLight ? colors.semantic.textPrimary : '#FFFFFF',
        secondary: isLight ? colors.semantic.textSecondary : 'rgba(255, 255, 255, 0.7)',
        disabled: isLight ? colors.semantic.textDisabled : 'rgba(255, 255, 255, 0.5)',
      },
      // Divider color from semantic tokens
      divider: isLight ? colors.semantic.borderDivider : 'rgba(255, 255, 255, 0.12)',
      // Action colors from semantic tokens
      action: {
        active: isLight ? colors.semantic.actionActive : 'rgba(255, 255, 255, 0.54)',
        hover: isLight ? colors.semantic.actionHover : 'rgba(255, 255, 255, 0.08)',
        selected: isLight ? colors.semantic.actionSelected : 'rgba(255, 255, 255, 0.16)',
        disabled: isLight ? colors.semantic.actionDisabled : 'rgba(255, 255, 255, 0.3)',
        disabledBackground: isLight
          ? colors.semantic.actionDisabledBackground
          : 'rgba(255, 255, 255, 0.12)',
      },
    },
    // Typography from design tokens
    typography: {
      fontFamily: typography.fontFamily.primary,
      // Heading styles from typography tokens
      h1: {
        fontSize: typography.fontSize.h1.rem,
        lineHeight: typography.fontSize.h1.lineHeight,
        fontWeight: typography.fontWeight.bold,
        letterSpacing: typography.letterSpacing.tight,
      },
      h2: {
        fontSize: typography.fontSize.h2.rem,
        lineHeight: typography.fontSize.h2.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.tight,
      },
      h3: {
        fontSize: typography.fontSize.h3.rem,
        lineHeight: typography.fontSize.h3.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.normal,
      },
      h4: {
        fontSize: typography.fontSize.h4.rem,
        lineHeight: typography.fontSize.h4.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.normal,
      },
      h5: {
        fontSize: typography.fontSize.h5.rem,
        lineHeight: typography.fontSize.h5.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.normal,
      },
      h6: {
        fontSize: typography.fontSize.h6.rem,
        lineHeight: typography.fontSize.h6.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.normal,
      },
      // Body text from typography tokens
      body1: {
        fontSize: typography.fontSize.body1.rem,
        lineHeight: typography.fontSize.body1.lineHeight,
        fontWeight: typography.fontWeight.regular,
        letterSpacing: typography.letterSpacing.normal,
      },
      body2: {
        fontSize: typography.fontSize.body2.rem,
        lineHeight: typography.fontSize.body2.lineHeight,
        fontWeight: typography.fontWeight.regular,
        letterSpacing: typography.letterSpacing.normal,
      },
      // Caption and overline from typography tokens
      caption: {
        fontSize: typography.fontSize.caption.rem,
        lineHeight: typography.fontSize.caption.lineHeight,
        fontWeight: typography.fontWeight.regular,
        letterSpacing: typography.letterSpacing.normal,
      },
      overline: {
        fontSize: typography.fontSize.overline.rem,
        lineHeight: typography.fontSize.overline.lineHeight,
        fontWeight: typography.fontWeight.semiBold,
        letterSpacing: typography.letterSpacing.wider,
        textTransform: 'uppercase' as const,
      },
      // Button text from typography tokens
      button: {
        fontSize: typography.fontSize.body2.rem,
        fontWeight: typography.fontWeight.medium,
        letterSpacing: typography.letterSpacing.wide,
        textTransform: 'none' as const,
      },
    },
    // Spacing from design tokens (4px base unit)
    spacing: 4, // Base spacing unit (4px)
    // Shape (border radius) from design tokens
    shape: {
      borderRadius: borderRadius.lg, // 8px default border radius
    },
    // Breakpoints from design system
    breakpoints: {
      values: {
        xs: 0, // Mobile (portrait)
        sm: 600, // Mobile (landscape), Tablet (portrait)
        md: 960, // Tablet (landscape)
        lg: 1280, // Desktop
        xl: 1920, // Large Desktop
      },
    },
    // Component overrides using design tokens
    components: {
      // Button component overrides
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.lg, // 8px
            textTransform: 'none',
            fontWeight: typography.fontWeight.medium,
            padding: `${spacing[2]}px ${spacing[4]}px`, // 8px 16px
            minWidth: '64px', // Minimum touch target
            boxShadow: 'none',
            '&:hover': {
              boxShadow: 'none',
            },
          },
          sizeSmall: {
            padding: `${spacing[1]}px ${spacing[3]}px`, // 4px 12px
            fontSize: typography.fontSize.caption.rem,
          },
          sizeLarge: {
            padding: `${spacing[3]}px ${spacing[6]}px`, // 12px 24px
            fontSize: typography.fontSize.body1.rem,
          },
          contained: {
            boxShadow: 'none',
            '&:hover': {
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
            },
          },
          outlined: {
            borderWidth: '1px',
            '&:hover': {
              borderWidth: '1px',
            },
          },
        },
      },
      // TextField component overrides
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: spacing[2], // 8px
              '& fieldset': {
                borderColor: colors.semantic.borderDefault,
              },
              '&:hover fieldset': {
                borderColor: colors.semantic.borderFocus,
              },
              '&.Mui-focused fieldset': {
                borderColor: colors.primary[500],
                borderWidth: '2px',
              },
              '&.Mui-error fieldset': {
                borderColor: colors.error[500],
              },
            },
            '& .MuiInputLabel-root': {
              fontSize: typography.fontSize.body2.rem,
            },
            '& .MuiInputBase-input': {
              fontSize: typography.fontSize.body1.rem,
              padding: `${spacing[3]}px ${spacing[4]}px`, // 12px 16px
            },
          },
        },
      },
      // Card component overrides
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.xl, // 12px
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
            padding: spacing[4], // 16px
            '&:hover': {
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              transition: 'box-shadow 0.2s ease-in-out',
            },
          },
        },
      },
      // CardContent component overrides
      MuiCardContent: {
        styleOverrides: {
          root: {
            padding: spacing[4], // 16px
            '&:last-child': {
              paddingBottom: spacing[4], // 16px
            },
          },
        },
      },
      // CardHeader component overrides
      MuiCardHeader: {
        styleOverrides: {
          root: {
            padding: spacing[4], // 16px
          },
          title: {
            fontSize: typography.fontSize.h5.rem,
            fontWeight: typography.fontWeight.semiBold,
          },
          subheader: {
            fontSize: typography.fontSize.body2.rem,
            color: colors.semantic.textSecondary,
          },
        },
      },
      // Paper component overrides
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.lg, // 8px
          },
          elevation1: {
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)',
          },
          elevation2: {
            boxShadow: '0 2px 6px rgba(0, 0, 0, 0.12)',
          },
          elevation3: {
            boxShadow: '0 3px 9px rgba(0, 0, 0, 0.12)',
          },
        },
      },
      // AppBar component overrides
      MuiAppBar: {
        styleOverrides: {
          root: {
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)',
          },
        },
      },
      // Chip component overrides
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.lg, // 8px
            height: '32px',
            fontSize: typography.fontSize.caption.rem,
            fontWeight: typography.fontWeight.medium,
          },
        },
      },
      // Dialog component overrides
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: borderRadius.xl, // 12px
          },
        },
      },
      // Drawer component overrides
      MuiDrawer: {
        styleOverrides: {
          paper: {
            borderRadius: `0 ${spacing[3]}px ${spacing[3]}px 0`, // 12px on right side
          },
        },
      },
      // ListItem component overrides
      MuiListItem: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.md, // 4px
            marginBottom: spacing[1], // 4px
            '&:hover': {
              backgroundColor: colors.semantic.actionHover,
            },
            '&.Mui-selected': {
              backgroundColor: colors.semantic.actionSelected,
              '&:hover': {
                backgroundColor: colors.semantic.actionSelected,
              },
            },
          },
        },
      },
      // Tooltip component overrides
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            borderRadius: borderRadius.md, // 4px
            fontSize: typography.fontSize.caption.rem,
            padding: `${spacing[1]}px ${spacing[2]}px`, // 4px 8px
          },
        },
      },
      // Alert component overrides
      MuiAlert: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.lg, // 8px
            fontSize: typography.fontSize.body2.rem,
          },
        },
      },
      // Snackbar component overrides
      MuiSnackbar: {
        styleOverrides: {
          root: {
            borderRadius: borderRadius.lg, // 8px
          },
        },
      },
      // Link component overrides
      MuiLink: {
        styleOverrides: {
          root: {
            textDecoration: 'none',
            '&:hover': {
              textDecoration: 'underline',
            },
          },
        },
      },
    },
  }

  return createTheme(themeOptions)
}

/**
 * Default light theme
 */
export const lightTheme = createAppTheme('light')

/**
 * Default dark theme
 */
export const darkTheme = createAppTheme('dark')

/**
 * Export theme type for use in components
 */
export type AppTheme = ReturnType<typeof createAppTheme>
