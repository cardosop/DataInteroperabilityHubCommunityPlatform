/**
 * ResponsiveTypography Component
 *
 * Typography component with fluid typography and responsive line-height adjustments.
 */

import React from 'react'
import { Typography, TypographyProps } from '@mui/material'
import { useTheme } from '@mui/material/styles'

export interface ResponsiveTypographyProps extends TypographyProps {
  /**
   * Responsive font sizes for different breakpoints
   */
  responsiveFontSize?: {
    xs?: string | number
    sm?: string | number
    md?: string | number
    lg?: string | number
    xl?: string | number
  }
  /**
   * Responsive line heights for different breakpoints
   */
  responsiveLineHeight?: {
    xs?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
  /**
   * Enable fluid typography (clamp)
   */
  fluid?: boolean
  /**
   * Minimum font size for fluid typography
   */
  minFontSize?: string
  /**
   * Maximum font size for fluid typography
   */
  maxFontSize?: string
}

/**
 * ResponsiveTypography component with fluid typography support
 */
export const ResponsiveTypography = React.forwardRef<
  HTMLSpanElement,
  ResponsiveTypographyProps
>(
  (
    {
      responsiveFontSize,
      responsiveLineHeight,
      fluid = false,
      minFontSize,
      maxFontSize,
      sx,
      ...props
    },
    ref
  ) => {
    const theme = useTheme()

    // Build responsive font size styles
    const responsiveFontSizeStyles = responsiveFontSize
      ? {
          fontSize: responsiveFontSize.xs || props.fontSize,
          [theme.breakpoints.up('sm')]: {
            fontSize: responsiveFontSize.sm || responsiveFontSize.xs || props.fontSize,
          },
          [theme.breakpoints.up('md')]: {
            fontSize: responsiveFontSize.md || responsiveFontSize.sm || props.fontSize,
          },
          [theme.breakpoints.up('lg')]: {
            fontSize: responsiveFontSize.lg || responsiveFontSize.md || props.fontSize,
          },
          [theme.breakpoints.up('xl')]: {
            fontSize: responsiveFontSize.xl || responsiveFontSize.lg || props.fontSize,
          },
        }
      : {}

    // Build responsive line height styles
    const responsiveLineHeightStyles = responsiveLineHeight
      ? {
          lineHeight: responsiveLineHeight.xs || props.lineHeight,
          [theme.breakpoints.up('sm')]: {
            lineHeight:
              responsiveLineHeight.sm || responsiveLineHeight.xs || props.lineHeight,
          },
          [theme.breakpoints.up('md')]: {
            lineHeight:
              responsiveLineHeight.md || responsiveLineHeight.sm || props.lineHeight,
          },
          [theme.breakpoints.up('lg')]: {
            lineHeight:
              responsiveLineHeight.lg || responsiveLineHeight.md || props.lineHeight,
          },
          [theme.breakpoints.up('xl')]: {
            lineHeight:
              responsiveLineHeight.xl || responsiveLineHeight.lg || props.lineHeight,
          },
        }
      : {}

    // Build fluid typography styles
    const fluidStyles = fluid && minFontSize && maxFontSize
      ? {
          fontSize: `clamp(${minFontSize}, 4vw, ${maxFontSize})`,
        }
      : {}

    return (
      <Typography
        ref={ref}
        sx={{
          ...responsiveFontSizeStyles,
          ...responsiveLineHeightStyles,
          ...fluidStyles,
          ...sx,
        }}
        {...props}
      />
    )
  }
)

ResponsiveTypography.displayName = 'ResponsiveTypography'

