/**
 * Touch Utilities
 *
 * Utility functions for touch-friendly interactions.
 */

/**
 * Minimum touch target size (Material Design)
 */
export const TOUCH_TARGET_MIN = 48 // pixels

/**
 * Minimum touch target size (iOS)
 */
export const TOUCH_TARGET_MIN_IOS = 44 // pixels

/**
 * Minimum spacing between touch targets
 */
export const TOUCH_TARGET_SPACING = 8 // pixels

/**
 * Check if device supports touch
 */
export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false
  return (
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0 ||
    // @ts-ignore - legacy support
    navigator.msMaxTouchPoints > 0
  )
}

/**
 * Get minimum touch target size based on platform
 */
export function getMinTouchTarget(): number {
  // Could be enhanced to detect iOS vs Android
  return TOUCH_TARGET_MIN
}

/**
 * Ensure element meets minimum touch target size
 */
export function ensureTouchTarget(
  width?: number | string,
  height?: number | string
): { width: number | string; height: number | string } {
  const minSize = getMinTouchTarget()
  const widthNum = typeof width === 'number' ? width : minSize
  const heightNum = typeof height === 'number' ? height : minSize

  return {
    width: Math.max(widthNum, minSize),
    height: Math.max(heightNum, minSize),
  }
}

