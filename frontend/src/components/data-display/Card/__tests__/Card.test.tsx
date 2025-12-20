/**
 * Card Component Tests
 *
 * Comprehensive tests for the Card component covering:
 * - Basic rendering
 * - Elevation levels
 * - Padding customization
 * - Hover effects
 * - Ref forwarding
 * - Custom styling
 * - Accessibility
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Card } from '../Card'

describe('Card', () => {
  describe('Basic Rendering', () => {
    it('should render children', () => {
      render(
        <Card>
          <div>Card Content</div>
        </Card>
      )
      expect(screen.getByText('Card Content')).toBeInTheDocument()
    })

    it('should render with default props', () => {
      const { container } = render(
        <Card>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card')
      expect(card).toBeInTheDocument()
      expect(card).toHaveClass('card')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <Card className="custom-class">
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card')
      expect(card).toHaveClass('custom-class')
    })
  })

  describe('Elevation Levels', () => {
    it('should apply elevation 1 by default', () => {
      const { container } = render(
        <Card>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card).toBeInTheDocument()
      // Check that elevation style is applied
      expect(card.style.boxShadow).toBeTruthy()
    })

    it('should apply elevation 2', () => {
      const { container } = render(
        <Card elevation={2}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card).toBeInTheDocument()
      expect(card.style.boxShadow).toBeTruthy()
    })

    it('should apply elevation 4', () => {
      const { container } = render(
        <Card elevation={4}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card).toBeInTheDocument()
      expect(card.style.boxShadow).toBeTruthy()
    })
  })

  describe('Padding Customization', () => {
    it('should apply default padding', () => {
      const { container } = render(
        <Card>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card.style.padding).toBeTruthy()
    })

    it('should apply custom padding', () => {
      const { container } = render(
        <Card padding={8}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card.style.padding).toBeTruthy()
    })
  })

  describe('Hover Effects', () => {
    it('should change elevation on hover for elevation 1', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <Card elevation={1}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      const initialShadow = card.style.boxShadow

      await user.hover(card)
      // After hover, shadow should change
      expect(card.style.boxShadow).not.toBe(initialShadow)

      await user.unhover(card)
      // After unhover, shadow should return to initial
      expect(card.style.boxShadow).toBe(initialShadow)
    })

    it('should not change elevation on hover for elevation 2', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <Card elevation={2}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      const initialShadow = card.style.boxShadow

      await user.hover(card)
      // Elevation 2 should not change on hover
      expect(card.style.boxShadow).toBe(initialShadow)
    })

    it('should not change elevation on hover for elevation 4', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <Card elevation={4}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      const initialShadow = card.style.boxShadow

      await user.hover(card)
      // Elevation 4 should not change on hover
      expect(card.style.boxShadow).toBe(initialShadow)
    })
  })

  describe('Ref Forwarding', () => {
    it('should forward ref to DOM element', () => {
      const ref = vi.fn()
      render(
        <Card ref={ref}>
          <div>Test</div>
        </Card>
      )
      expect(ref).toHaveBeenCalled()
      expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLDivElement)
    })
  })

  describe('Custom Styling', () => {
    it('should merge custom styles', () => {
      const { container } = render(
        <Card style={{ backgroundColor: 'red' }}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card.style.backgroundColor).toBe('red')
    })

    it('should preserve default styles when custom styles are applied', () => {
      const { container } = render(
        <Card style={{ backgroundColor: 'blue' }}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card.style.backgroundColor).toBe('blue')
      // borderRadius should be set by the component (from borderRadius.lg = 8)
      // React converts the number 8 to "8px" in the style
      // The component sets borderRadius before spreading props.style, so it should be present
      // Check that borderRadius is set (React converts number to "8px")
      const borderRadiusValue = card.style.borderRadius
      // borderRadius.lg is 8, which React converts to "8px"
      expect(borderRadiusValue).toBe('8px')
    })
  })

  describe('HTML Attributes', () => {
    it('should pass through HTML attributes', () => {
      const { container } = render(
        <Card data-testid="card" aria-label="Test Card">
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      expect(card.getAttribute('data-testid')).toBe('card')
      expect(card.getAttribute('aria-label')).toBe('Test Card')
    })

    it('should handle onClick events', async () => {
      const handleClick = vi.fn()
      const { container } = render(
        <Card onClick={handleClick}>
          <div>Test</div>
        </Card>
      )
      const card = container.querySelector('.card') as HTMLElement
      await userEvent.click(card)
      expect(handleClick).toHaveBeenCalledTimes(1)
    })
  })
})

