/**
 * Responsive Utilities
 *
 * Helper functions for responsive design patterns.
 */

import { breakpoints } from '@/hooks/useMediaQuery'

export type BreakpointKey = keyof typeof breakpoints

/**
 * Get breakpoint value in pixels
 */
export function getBreakpointValue(breakpoint: BreakpointKey): number {
  return breakpoints[breakpoint]
}

/**
 * Create media query string for min-width
 */
export function minWidth(breakpoint: BreakpointKey | number): string {
  const value = typeof breakpoint === 'number' ? breakpoint : breakpoints[breakpoint]
  return `(min-width: ${value}px)`
}

/**
 * Create media query string for max-width
 */
export function maxWidth(breakpoint: BreakpointKey | number): string {
  const value = typeof breakpoint === 'number' ? breakpoint : breakpoints[breakpoint]
  return `(max-width: ${value - 1}px)`
}

/**
 * Create media query string for range
 */
export function between(
  min: BreakpointKey | number,
  max: BreakpointKey | number
): string {
  const minValue = typeof min === 'number' ? min : breakpoints[min]
  const maxValue = typeof max === 'number' ? max : breakpoints[max]
  return `(min-width: ${minValue}px) and (max-width: ${maxValue - 1}px)`
}

/**
 * Check if current viewport matches breakpoint (client-side only)
 */
export function matchesBreakpoint(breakpoint: BreakpointKey): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia(minWidth(breakpoint)).matches
}

/**
 * Check if viewport is mobile (320-767px)
 */
export function isMobile(): boolean {
  if (typeof window === 'undefined') return false
  const width = window.innerWidth
  return width >= breakpoints.mobile && width <= breakpoints.mobileMax
}

/**
 * Check if viewport is tablet (768-1023px)
 */
export function isTablet(): boolean {
  if (typeof window === 'undefined') return false
  const width = window.innerWidth
  return width >= breakpoints.tablet && width <= breakpoints.tabletMax
}

/**
 * Check if viewport is desktop (1024px+)
 */
export function isDesktop(): boolean {
  if (typeof window === 'undefined') return false
  return window.innerWidth >= breakpoints.desktop
}

/**
 * Get responsive value based on breakpoint
 */
export function getResponsiveValue<T>(
  values: Partial<Record<BreakpointKey, T>>,
  defaultValue: T
): T {
  if (typeof window === 'undefined') return defaultValue

  const width = window.innerWidth
  const breakpointOrder: BreakpointKey[] = ['xl', 'lg', 'desktop', 'md', 'tablet', 'sm', 'xs']

  for (const bp of breakpointOrder) {
    if (width >= breakpoints[bp] && values[bp] !== undefined) {
      return values[bp] as T
    }
  }

  return defaultValue
}

