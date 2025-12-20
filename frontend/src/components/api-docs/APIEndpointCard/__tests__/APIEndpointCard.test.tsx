/**
 * APIEndpointCard Tests
 *
 * Comprehensive tests for the APIEndpointCard component covering:
 * - Endpoint information display
 * - Method badge rendering
 * - Path display
 * - Description display
 * - Selection state
 * - Click handling
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { APIEndpointCard } from '../APIEndpointCard'
import type { APIEndpoint } from '../types'

const mockEndpoint: APIEndpoint = {
  method: 'GET',
  path: '/api/v1/assets/',
  description: 'List all assets',
  parameters: {
    query: [
      { name: 'page', type: 'integer', required: false, description: 'Page number' },
    ],
  },
  responses: [
    {
      status: 200,
      description: 'Success',
      example: { results: [] },
    },
  ],
}

describe('APIEndpointCard', () => {
  describe('Rendering', () => {
    it('should render endpoint method', () => {
      render(<APIEndpointCard endpoint={mockEndpoint} onClick={vi.fn()} />)
      expect(screen.getByText('GET')).toBeInTheDocument()
    })

    it('should render endpoint path', () => {
      render(<APIEndpointCard endpoint={mockEndpoint} onClick={vi.fn()} />)
      expect(screen.getByText('/api/v1/assets/')).toBeInTheDocument()
    })

    it('should render endpoint description', () => {
      render(<APIEndpointCard endpoint={mockEndpoint} onClick={vi.fn()} />)
      expect(screen.getByText('List all assets')).toBeInTheDocument()
    })

    it('should render different HTTP methods correctly', () => {
      const postEndpoint = { ...mockEndpoint, method: 'POST' as const }
      const { rerender } = render(<APIEndpointCard endpoint={postEndpoint} onClick={vi.fn()} />)
      expect(screen.getByText('POST')).toBeInTheDocument()

      const putEndpoint = { ...mockEndpoint, method: 'PUT' as const }
      rerender(<APIEndpointCard endpoint={putEndpoint} onClick={vi.fn()} />)
      expect(screen.getByText('PUT')).toBeInTheDocument()
    })
  })

  describe('Selection State', () => {
    it('should apply selected styles when selected', () => {
      const { container } = render(
        <APIEndpointCard endpoint={mockEndpoint} onClick={vi.fn()} selected />
      )
      const card = container.querySelector('.MuiCard-root')
      expect(card).toHaveStyle({ borderWidth: '2px' })
    })

    it('should not apply selected styles when not selected', () => {
      const { container } = render(
        <APIEndpointCard endpoint={mockEndpoint} onClick={vi.fn()} selected={false} />
      )
      const card = container.querySelector('.MuiCard-root')
      expect(card).toHaveStyle({ borderWidth: '1px' })
    })
  })

  describe('Interactions', () => {
    it('should call onClick when card is clicked', () => {
      const handleClick = vi.fn()
      const { container } = render(
        <APIEndpointCard endpoint={mockEndpoint} onClick={handleClick} />
      )
      const card = container.querySelector('.MuiCard-root')
      fireEvent.click(card!)
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('should pass endpoint to onClick handler', () => {
      const handleClick = vi.fn()
      const { container } = render(
        <APIEndpointCard endpoint={mockEndpoint} onClick={handleClick} />
      )
      const card = container.querySelector('.MuiCard-root')
      fireEvent.click(card!)
      expect(handleClick).toHaveBeenCalledWith(mockEndpoint)
    })
  })
})

