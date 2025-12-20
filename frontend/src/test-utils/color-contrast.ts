/**
 * Color Contrast Testing Utilities
 *
 * Utilities for testing color contrast ratios for WCAG compliance.
 * WCAG 2.1 Level AA requires:
 * - 4.5:1 for normal text (≤18px)
 * - 3:1 for large text (>18px or bold ≥14px)
 * - 3:1 for UI components and graphical objects
 */

/**
 * Convert hex color to RGB
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null
}

/**
 * Calculate relative luminance
 * Based on WCAG 2.1 formula
 */
function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((val) => {
    val = val / 255
    return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
}

/**
 * Calculate contrast ratio between two colors
 * Based on WCAG 2.1 formula
 */
export function calculateContrastRatio(
  color1: string,
  color2: string
): number {
  const rgb1 = hexToRgb(color1)
  const rgb2 = hexToRgb(color2)

  if (!rgb1 || !rgb2) {
    throw new Error('Invalid color format. Use hex colors (e.g., #ffffff)')
  }

  const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b)
  const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b)

  const lighter = Math.max(lum1, lum2)
  const darker = Math.min(lum1, lum2)

  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Check if contrast ratio meets WCAG AA standards
 */
export function meetsWCAGAA(
  foreground: string,
  background: string,
  isLargeText: boolean = false
): boolean {
  const ratio = calculateContrastRatio(foreground, background)
  return isLargeText ? ratio >= 3.0 : ratio >= 4.5
}

/**
 * Check if contrast ratio meets WCAG AAA standards
 */
export function meetsWCAGAAA(
  foreground: string,
  background: string,
  isLargeText: boolean = false
): boolean {
  const ratio = calculateContrastRatio(foreground, background)
  return isLargeText ? ratio >= 4.5 : ratio >= 7.0
}

/**
 * Get computed text color and background color from an element
 */
export function getElementColors(element: HTMLElement): {
  foreground: string
  background: string
} {
  const styles = window.getComputedStyle(element)
  const foreground = styles.color
  const background =
    styles.backgroundColor ||
    styles.background ||
    getComputedStyle(document.body).backgroundColor

  // Convert rgb/rgba to hex
  const rgbToHex = (rgb: string): string => {
    const match = rgb.match(/\d+/g)
    if (!match || match.length < 3) return '#000000'
    const [r, g, b] = match.map(Number)
    return `#${[r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('')}`
  }

  return {
    foreground: rgbToHex(foreground),
    background: rgbToHex(background),
  }
}

/**
 * Check if an element's text meets WCAG AA contrast requirements
 */
export function checkElementContrast(
  element: HTMLElement,
  isLargeText: boolean = false
): { passes: boolean; ratio: number; required: number } {
  const colors = getElementColors(element)
  const ratio = calculateContrastRatio(colors.foreground, colors.background)
  const required = isLargeText ? 3.0 : 4.5

  return {
    passes: ratio >= required,
    ratio,
    required,
  }
}

