/**
 * CardContent Component Tests
 *
 * Comprehensive tests for the CardContent component covering:
 * - Basic rendering
 * - Children rendering
 * - Custom styling
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CardContent } from '../CardContent'

describe('CardContent', () => {
  describe('Basic Rendering', () => {
    it('should render children', () => {
      render(
        <CardContent>
          <div>Content</div>
        </CardContent>
      )
      expect(screen.getByText('Content')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <CardContent className="custom-class">
          <div>Test</div>
        </CardContent>
      )
      const content = container.querySelector('.card-content')
      expect(content).toHaveClass('custom-class')
    })
  })

  describe('HTML Attributes', () => {
    it('should pass through HTML attributes', () => {
      const { container } = render(
        <CardContent data-testid="content" id="test-content">
          <div>Test</div>
        </CardContent>
      )
      const content = container.querySelector('.card-content')
      expect(content?.getAttribute('data-testid')).toBe('content')
      expect(content?.getAttribute('id')).toBe('test-content')
    })
  })
})

