/**
 * Badge Component Tests
 *
 * Comprehensive tests for the Badge component covering:
 * - Basic rendering
 * - Variant styles
 * - Size variants
 * - Custom className
 * - Children rendering
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '../Badge'

describe('Badge', () => {
  describe('Basic Rendering', () => {
    it('should render children', () => {
      render(<Badge>Badge Content</Badge>)
      expect(screen.getByText('Badge Content')).toBeInTheDocument()
    })

    it('should render with default props', () => {
      const { container } = render(<Badge>Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveClass('badge-neutral')
    })

    it('should apply custom className', () => {
      const { container } = render(<Badge className="custom-class">Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('custom-class')
    })
  })

  describe('Variants', () => {
    it('should apply neutral variant by default', () => {
      const { container } = render(<Badge>Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('badge-neutral')
    })

    it('should apply success variant', () => {
      const { container } = render(<Badge variant="success">Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('badge-success')
    })

    it('should apply warning variant', () => {
      const { container } = render(<Badge variant="warning">Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('badge-warning')
    })

    it('should apply error variant', () => {
      const { container } = render(<Badge variant="error">Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('badge-error')
    })

    it('should apply info variant', () => {
      const { container } = render(<Badge variant="info">Test</Badge>)
      const badge = container.querySelector('.badge')
      expect(badge).toHaveClass('badge-info')
    })
  })

  describe('Sizes', () => {
    it('should apply medium size by default', () => {
      const { container } = render(<Badge>Test</Badge>)
      const badge = container.querySelector('.badge') as HTMLElement
      expect(badge.style.height).toBe('24px')
      expect(badge.style.fontSize).toBe('12px')
    })

    it('should apply small size', () => {
      const { container } = render(<Badge size="sm">Test</Badge>)
      const badge = container.querySelector('.badge') as HTMLElement
      expect(badge.style.height).toBe('20px')
      expect(badge.style.fontSize).toBe('11px')
    })
  })

  describe('Styling', () => {
    it('should apply inline-flex display', () => {
      const { container } = render(<Badge>Test</Badge>)
      const badge = container.querySelector('.badge') as HTMLElement
      expect(badge.style.display).toBe('inline-flex')
    })

    it('should apply full border radius', () => {
      const { container } = render(<Badge>Test</Badge>)
      const badge = container.querySelector('.badge') as HTMLElement
      expect(badge.style.borderRadius).toBeTruthy()
    })
  })
})

