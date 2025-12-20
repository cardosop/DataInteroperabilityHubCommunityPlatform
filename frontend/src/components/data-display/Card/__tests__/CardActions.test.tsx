/**
 * CardActions Component Tests
 *
 * Comprehensive tests for the CardActions component covering:
 * - Basic rendering
 * - Children rendering
 * - Custom styling
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CardActions } from '../CardActions'

describe('CardActions', () => {
  describe('Basic Rendering', () => {
    it('should render children', () => {
      render(
        <CardActions>
          <button>Action 1</button>
          <button>Action 2</button>
        </CardActions>
      )
      expect(screen.getByText('Action 1')).toBeInTheDocument()
      expect(screen.getByText('Action 2')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <CardActions className="custom-class">
          <button>Action</button>
        </CardActions>
      )
      const actions = container.querySelector('.card-actions')
      expect(actions).toHaveClass('custom-class')
    })
  })

  describe('Styling', () => {
    it('should apply flex layout', () => {
      const { container } = render(
        <CardActions>
          <button>Action</button>
        </CardActions>
      )
      const actions = container.querySelector('.card-actions') as HTMLElement
      expect(actions.style.display).toBe('flex')
    })

    it('should merge custom styles', () => {
      const { container } = render(
        <CardActions style={{ justifyContent: 'center' }}>
          <button>Action</button>
        </CardActions>
      )
      const actions = container.querySelector('.card-actions') as HTMLElement
      expect(actions.style.justifyContent).toBe('center')
    })
  })
})

