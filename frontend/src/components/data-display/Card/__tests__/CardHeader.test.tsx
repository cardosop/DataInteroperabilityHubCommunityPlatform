/**
 * CardHeader Component Tests
 *
 * Comprehensive tests for the CardHeader component covering:
 * - Basic rendering
 * - Title and subtitle display
 * - Actions rendering
 * - Children rendering
 * - Custom styling
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CardHeader } from '../CardHeader'

describe('CardHeader', () => {
  describe('Basic Rendering', () => {
    it('should render with children', () => {
      render(
        <CardHeader>
          <div>Header Content</div>
        </CardHeader>
      )
      expect(screen.getByText('Header Content')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <CardHeader className="custom-class">
          <div>Test</div>
        </CardHeader>
      )
      const header = container.querySelector('.card-header')
      expect(header).toHaveClass('custom-class')
    })
  })

  describe('Title and Subtitle', () => {
    it('should render title when provided', () => {
      render(<CardHeader title="Test Title" />)
      expect(screen.getByText('Test Title')).toBeInTheDocument()
    })

    it('should render subtitle when provided', () => {
      render(<CardHeader subtitle="Test Subtitle" />)
      expect(screen.getByText('Test Subtitle')).toBeInTheDocument()
    })

    it('should render both title and subtitle', () => {
      render(<CardHeader title="Title" subtitle="Subtitle" />)
      expect(screen.getByText('Title')).toBeInTheDocument()
      expect(screen.getByText('Subtitle')).toBeInTheDocument()
    })

    it('should not render title when not provided', () => {
      render(<CardHeader subtitle="Subtitle" />)
      // Use a more specific query that won't match "Subtitle"
      // Check that no element with the title styling exists
      const titleElement = screen.queryByText('Title')
      expect(titleElement).not.toBeInTheDocument()
      // Verify subtitle is still rendered
      expect(screen.getByText('Subtitle')).toBeInTheDocument()
    })

    it('should not render subtitle when not provided', () => {
      render(<CardHeader title="Title" />)
      expect(screen.queryByText(/subtitle/i)).not.toBeInTheDocument()
    })
  })

  describe('Actions', () => {
    it('should render actions when provided', () => {
      render(
        <CardHeader
          title="Title"
          actions={<button>Action</button>}
        />
      )
      expect(screen.getByText('Action')).toBeInTheDocument()
    })

    it('should not render actions when not provided', () => {
      render(<CardHeader title="Title" />)
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('Styling', () => {
    it('should apply flex layout', () => {
      const { container } = render(<CardHeader title="Title" />)
      const header = container.querySelector('.card-header') as HTMLElement
      expect(header.style.display).toBe('flex')
    })

    it('should merge custom styles', () => {
      const { container } = render(
        <CardHeader title="Title" style={{ backgroundColor: 'red' }} />
      )
      const header = container.querySelector('.card-header') as HTMLElement
      expect(header.style.backgroundColor).toBe('red')
    })
  })
})

