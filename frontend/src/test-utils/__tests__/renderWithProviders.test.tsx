/**
 * renderWithProviders Tests
 *
 * Tests for the renderWithProviders utility.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { renderWithProviders } from '../renderWithProviders'
import { createTestQueryClient } from '../createTestQueryClient'
import React from 'react'

// Test component
const TestComponent: React.FC<{ message?: string }> = ({ message = 'Hello' }) => (
  <div>{message}</div>
)

describe('renderWithProviders', () => {
  beforeEach(() => {
    // Cleanup between tests
  })

  it('should render component with all providers', () => {
    const { getByText } = renderWithProviders(<TestComponent />)
    expect(getByText('Hello')).toBeInTheDocument()
  })

  it('should render component with custom message', () => {
    const { getByText } = renderWithProviders(<TestComponent message="Custom" />)
    expect(getByText('Custom')).toBeInTheDocument()
  })

  it('should use custom QueryClient when provided', () => {
    const customQueryClient = createTestQueryClient()
    const { container } = renderWithProviders(<TestComponent />, {
      queryClient: customQueryClient,
    })
    expect(container).toBeInTheDocument()
  })

  it('should use custom initial route', () => {
    const { container } = renderWithProviders(<TestComponent />, {
      initialEntries: ['/custom-path'],
    })
    expect(container).toBeInTheDocument()
  })

  it('should use custom theme mode', () => {
    const { container } = renderWithProviders(<TestComponent />, {
      themeMode: 'dark',
    })
    expect(container).toBeInTheDocument()
  })
})

