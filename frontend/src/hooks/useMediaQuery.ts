/**
 * useMediaQuery Hook
 *
 * React hook for responsive design using media queries.
 * Provides breakpoint matching and custom media query support.
 */

import { useState, useEffect } from 'react'
import { useTheme } from '@mui/material/styles'
import { useMediaQuery as useMuiMediaQuery } from '@mui/material'

/**
 * Breakpoint definitions matching design system
 * Mobile: 320-767px
 * Tablet: 768-1023px
 * Desktop: 1024px+
 */
export const breakpoints = {
  xs: 0, // Extra small (phones, < 600px)
  sm: 600, // Small (large phones, small tablets)
  mobile: 320, // Mobile start
  mobileMax: 767, // Mobile end
  tablet: 768, // Tablet start
  tabletMax: 1023, // Tablet end
  desktop: 1024, // Desktop start
  md: 960, // Medium (tablets)
  lg: 1280, // Large (desktops)
  xl: 1920, // Extra large (large desktops)
} as const

export type BreakpointKey = keyof typeof breakpoints

/**
 * Hook to check if current viewport matches a breakpoint
 */
export function useMediaQuery(breakpoint: BreakpointKey | number): boolean {
  const theme = useTheme()
  const query = typeof breakpoint === 'number'
    ? `(min-width: ${breakpoint}px)`
    : `(min-width: ${breakpoints[breakpoint]}px)`

  return useMuiMediaQuery(query)
}

/**
 * Hook to check if viewport is mobile (320-767px)
 */
export function useIsMobile(): boolean {
  const isMobileMin = useMediaQuery(breakpoints.mobile)
  const isMobileMax = useMediaQuery(breakpoints.tablet)
  return isMobileMin && !isMobileMax
}

/**
 * Hook to check if viewport is tablet (768-1023px)
 */
export function useIsTablet(): boolean {
  const isTabletMin = useMediaQuery(breakpoints.tablet)
  const isTabletMax = useMediaQuery(breakpoints.desktop)
  return isTabletMin && !isTabletMax
}

/**
 * Hook to check if viewport is desktop (1024px+)
 */
export function useIsDesktop(): boolean {
  return useMediaQuery(breakpoints.desktop)
}

/**
 * Hook to get current breakpoint name
 */
export function useBreakpoint(): BreakpointKey {
  const theme = useTheme()
  const [breakpoint, setBreakpoint] = useState<BreakpointKey>('xs')

  useEffect(() => {
    const updateBreakpoint = () => {
      const width = window.innerWidth
      if (width >= breakpoints.xl) setBreakpoint('xl')
      else if (width >= breakpoints.lg) setBreakpoint('lg')
      else if (width >= breakpoints.desktop) setBreakpoint('desktop')
      else if (width >= breakpoints.md) setBreakpoint('md')
      else if (width >= breakpoints.tablet) setBreakpoint('tablet')
      else if (width >= breakpoints.sm) setBreakpoint('sm')
      else setBreakpoint('xs')
    }

    updateBreakpoint()
    window.addEventListener('resize', updateBreakpoint)
    return () => window.removeEventListener('resize', updateBreakpoint)
  }, [])

  return breakpoint
}

/**
 * Hook for custom media queries
 */
export function useCustomMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    setMatches(mediaQuery.matches)

    const handler = (event: MediaQueryListEvent) => setMatches(event.matches)
    mediaQuery.addEventListener('change', handler)

    return () => mediaQuery.removeEventListener('change', handler)
  }, [query])

  return matches
}

