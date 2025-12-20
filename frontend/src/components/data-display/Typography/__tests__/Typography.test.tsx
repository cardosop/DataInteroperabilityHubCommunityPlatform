/**
 * Typography Component Tests
 *
 * Comprehensive tests for the Typography component covering:
 * - Basic rendering
 * - Variant rendering
 * - Component prop
 * - Custom styling
 * - HTML attributes
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Typography } from '../Typography'

describe('Typography', () => {
  describe('Basic Rendering', () => {
    it('should render children', () => {
      render(<Typography>Typography Content</Typography>)
      expect(screen.getByText('Typography Content')).toBeInTheDocument()
    })

    it('should render with default props', () => {
      const { container } = render(<Typography>Test</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toBeInTheDocument()
      expect(typography).toHaveClass('typography-body1')
      expect(typography?.tagName).toBe('P')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <Typography className="custom-class">Test</Typography>
      )
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('custom-class')
    })
  })

  describe('Variants', () => {
    it('should render h1 variant', () => {
      const { container } = render(<Typography variant="h1">Heading 1</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h1')
      expect(typography?.tagName).toBe('H1')
    })

    it('should render h2 variant', () => {
      const { container } = render(<Typography variant="h2">Heading 2</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h2')
      expect(typography?.tagName).toBe('H2')
    })

    it('should render h3 variant', () => {
      const { container } = render(<Typography variant="h3">Heading 3</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h3')
      expect(typography?.tagName).toBe('H3')
    })

    it('should render h4 variant', () => {
      const { container } = render(<Typography variant="h4">Heading 4</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h4')
      expect(typography?.tagName).toBe('H4')
    })

    it('should render h5 variant', () => {
      const { container } = render(<Typography variant="h5">Heading 5</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h5')
      expect(typography?.tagName).toBe('H5')
    })

    it('should render h6 variant', () => {
      const { container } = render(<Typography variant="h6">Heading 6</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-h6')
      expect(typography?.tagName).toBe('H6')
    })

    it('should render body1 variant', () => {
      const { container } = render(<Typography variant="body1">Body 1</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-body1')
      expect(typography?.tagName).toBe('P')
    })

    it('should render body2 variant', () => {
      const { container } = render(<Typography variant="body2">Body 2</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-body2')
      expect(typography?.tagName).toBe('P')
    })

    it('should render caption variant', () => {
      const { container } = render(<Typography variant="caption">Caption</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-caption')
      expect(typography?.tagName).toBe('SPAN')
    })

    it('should render overline variant', () => {
      const { container } = render(<Typography variant="overline">Overline</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-overline')
      expect(typography?.tagName).toBe('SPAN')
    })

    it('should render code variant', () => {
      const { container } = render(<Typography variant="code">Code</Typography>)
      const typography = container.querySelector('.typography')
      expect(typography).toHaveClass('typography-code')
      expect(typography?.tagName).toBe('CODE')
    })
  })

  describe('Component Prop', () => {
    it('should render as custom component', () => {
      const { container } = render(
        <Typography component="div">Test</Typography>
      )
      const typography = container.querySelector('.typography')
      expect(typography?.tagName).toBe('DIV')
    })

    it('should override variant default component', () => {
      const { container } = render(
        <Typography variant="h1" component="div">
          Test
        </Typography>
      )
      const typography = container.querySelector('.typography')
      expect(typography?.tagName).toBe('DIV')
    })
  })

  describe('Styling', () => {
    it('should apply variant-specific font size', () => {
      const { container } = render(<Typography variant="h1">Test</Typography>)
      const typography = container.querySelector('.typography') as HTMLElement
      expect(typography.style.fontSize).toBeTruthy()
    })

    it('should apply monospace font for code variant', () => {
      const { container } = render(<Typography variant="code">Test</Typography>)
      const typography = container.querySelector('.typography') as HTMLElement
      expect(typography.style.fontFamily).toBeTruthy()
    })

    it('should merge custom styles', () => {
      const { container } = render(
        <Typography style={{ color: 'red' }}>Test</Typography>
      )
      const typography = container.querySelector('.typography') as HTMLElement
      expect(typography.style.color).toBe('red')
    })
  })

  describe('HTML Attributes', () => {
    it('should pass through HTML attributes', () => {
      const { container } = render(
        <Typography data-testid="typography" id="test-typography">
          Test
        </Typography>
      )
      const typography = container.querySelector('.typography')
      expect(typography?.getAttribute('data-testid')).toBe('typography')
      expect(typography?.getAttribute('id')).toBe('test-typography')
    })

    it('should handle onClick events', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()
      render(<Typography onClick={handleClick}>Test</Typography>)
      const typography = screen.getByText('Test')
      await user.click(typography)
      expect(handleClick).toHaveBeenCalled()
    })
  })
})

