/**
 * Color Contrast Tests
 *
 * Comprehensive color contrast tests for WCAG 2.1 Level AA compliance.
 * Tests:
 * - Text contrast (4.5:1 for normal text, 3:1 for large text)
 * - Interactive element contrast (3:1)
 * - Error state contrast
 *
 * Uses real color contrast calculations (no mocks/stubs)
 */

import { describe, it, expect } from 'vitest'
import { render } from '@/test-utils'
import {
  calculateContrastRatio,
  meetsWCAGAA,
  checkElementContrast,
} from '@/test-utils/color-contrast'
import { Button } from '@mui/material'
import { ThemeProvider, createTheme } from '@mui/material/styles'

describe('Color Contrast Tests', () => {
  describe('Contrast Ratio Calculations', () => {
    it('should calculate contrast ratio correctly', () => {
      // Black on white should have high contrast
      const ratio = calculateContrastRatio('#000000', '#ffffff')
      expect(ratio).toBeGreaterThan(20)

      // White on black should have high contrast
      const ratio2 = calculateContrastRatio('#ffffff', '#000000')
      expect(ratio2).toBeGreaterThan(20)
    })

    it('should meet WCAG AA for normal text', () => {
      // Black on white meets AA
      expect(meetsWCAGAA('#000000', '#ffffff', false)).toBe(true)

      // Dark gray on white should meet AA
      expect(meetsWCAGAA('#333333', '#ffffff', false)).toBe(true)
    })

    it('should meet WCAG AA for large text', () => {
      // Lighter colors can meet AA for large text
      expect(meetsWCAGAA('#666666', '#ffffff', true)).toBe(true)
    })

    it('should fail WCAG AA for low contrast', () => {
      // Light gray on white fails AA
      expect(meetsWCAGAA('#cccccc', '#ffffff', false)).toBe(false)
    })
  })

  describe('Text Contrast', () => {
    it('should have sufficient contrast for normal text', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <p style={{ color: '#000000', backgroundColor: '#ffffff' }}>
            Normal text
          </p>
        </ThemeProvider>
      )

      const textElement = container.querySelector('p')
      if (textElement) {
        const result = checkElementContrast(textElement, false)
        expect(result.passes).toBe(true)
        expect(result.ratio).toBeGreaterThanOrEqual(4.5)
      }
    })

    it('should have sufficient contrast for large text', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <h1 style={{ color: '#000000', backgroundColor: '#ffffff', fontSize: '24px' }}>
            Large text
          </h1>
        </ThemeProvider>
      )

      const textElement = container.querySelector('h1')
      if (textElement) {
        const result = checkElementContrast(textElement, true)
        expect(result.passes).toBe(true)
        expect(result.ratio).toBeGreaterThanOrEqual(3.0)
      }
    })
  })

  describe('Interactive Element Contrast', () => {
    it('should have sufficient contrast for buttons', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <Button
            variant="contained"
            style={{ color: '#ffffff', backgroundColor: '#1976d2' }}
          >
            Button
          </Button>
        </ThemeProvider>
      )

      const button = container.querySelector('button')
      if (button) {
        const result = checkElementContrast(button, false)
        // Buttons should meet 3:1 contrast (UI components)
        expect(result.ratio).toBeGreaterThanOrEqual(3.0)
      }
    })

    it('should have sufficient contrast for links', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <a
            href="#"
            style={{ color: '#1976d2', backgroundColor: '#ffffff' }}
          >
            Link
          </a>
        </ThemeProvider>
      )

      const link = container.querySelector('a')
      if (link) {
        const result = checkElementContrast(link, false)
        // Links should meet 4.5:1 contrast (normal text)
        expect(result.ratio).toBeGreaterThanOrEqual(4.5)
      }
    })
  })

  describe('Error State Contrast', () => {
    it('should have sufficient contrast for error text', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <p
            style={{
              color: '#d32f2f',
              backgroundColor: '#ffffff',
            }}
          >
            Error message
          </p>
        </ThemeProvider>
      )

      const errorElement = container.querySelector('p')
      if (errorElement) {
        const result = checkElementContrast(errorElement, false)
        // Error messages should be readable
        expect(result.ratio).toBeGreaterThanOrEqual(4.5)
      }
    })

    it('should have sufficient contrast for error backgrounds', () => {
      const { container } = render(
        <ThemeProvider theme={createTheme()}>
          <div
            style={{
              color: '#ffffff',
              backgroundColor: '#d32f2f',
              padding: '8px',
            }}
          >
            Error on red background
          </div>
        </ThemeProvider>
      )

      const errorElement = container.querySelector('div')
      if (errorElement) {
        const result = checkElementContrast(errorElement, false)
        // Error backgrounds should have readable text
        expect(result.ratio).toBeGreaterThanOrEqual(4.5)
      }
    })
  })

  describe('Common Color Combinations', () => {
    it('should test common text color combinations', () => {
      const combinations = [
        { fg: '#000000', bg: '#ffffff', expected: true }, // Black on white
        { fg: '#ffffff', bg: '#000000', expected: true }, // White on black
        { fg: '#333333', bg: '#ffffff', expected: true }, // Dark gray on white
        { fg: '#666666', bg: '#ffffff', expected: true }, // Medium gray on white
        { fg: '#cccccc', bg: '#ffffff', expected: false }, // Light gray on white (fails)
      ]

      combinations.forEach(({ fg, bg, expected }) => {
        expect(meetsWCAGAA(fg, bg, false)).toBe(expected)
      })
    })

    it('should test Material-UI theme colors', () => {
      // Test common MUI color combinations
      const muiCombinations = [
        { fg: '#ffffff', bg: '#1976d2', expected: true }, // Primary button
        { fg: '#1976d2', bg: '#ffffff', expected: true }, // Primary text
        { fg: '#ffffff', bg: '#d32f2f', expected: true }, // Error button
      ]

      muiCombinations.forEach(({ fg, bg, expected }) => {
        expect(meetsWCAGAA(fg, bg, false)).toBe(expected)
      })
    })
  })
})

