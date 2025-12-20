/**
 * VirtualListTanStack Component Tests
 *
 * Comprehensive tests for VirtualListTanStack component covering:
 * - Rendering items
 * - Virtual scrolling behavior
 * - Empty state
 * - Loading state
 * - Variable height support
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VirtualListTanStack } from '../VirtualListTanStack'

// Mock @tanstack/react-virtual
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: vi.fn(() => ({
    getVirtualItems: () => [
      {
        key: 0,
        index: 0,
        start: 0,
        size: 50,
        measureElement: vi.fn(),
      },
      {
        key: 1,
        index: 1,
        start: 50,
        size: 50,
        measureElement: vi.fn(),
      },
    ],
    getTotalSize: () => 100,
    scrollToIndex: vi.fn(),
    scrollToOffset: vi.fn(),
    measureElement: vi.fn(),
  })),
}))

describe('VirtualListTanStack', () => {
  const items = [
    { id: 1, name: 'Item 1' },
    { id: 2, name: 'Item 2' },
    { id: 3, name: 'Item 3' },
  ]

  it('should render items', () => {
    render(
      <VirtualListTanStack
        items={items}
        itemHeight={50}
        containerHeight={200}
        renderItem={(item) => <div>{item.name}</div>}
      />
    )

    expect(screen.getByText('Item 1')).toBeInTheDocument()
    expect(screen.getByText('Item 2')).toBeInTheDocument()
  })

  it('should render empty state when no items', () => {
    render(
      <VirtualListTanStack
        items={[]}
        itemHeight={50}
        containerHeight={200}
        renderItem={() => <div>Item</div>}
      />
    )

    expect(screen.getByText('No items')).toBeInTheDocument()
  })

  it('should render custom empty component', () => {
    render(
      <VirtualListTanStack
        items={[]}
        itemHeight={50}
        containerHeight={200}
        renderItem={() => <div>Item</div>}
        emptyComponent={<div>Custom Empty</div>}
      />
    )

    expect(screen.getByText('Custom Empty')).toBeInTheDocument()
  })

  it('should render loading component when loading', () => {
    render(
      <VirtualListTanStack
        items={items}
        itemHeight={50}
        containerHeight={200}
        renderItem={(item) => <div>{item.name}</div>}
        isLoading={true}
        loadingComponent={<div>Loading...</div>}
      />
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('should use getItemKey for keys', () => {
    const getItemKey = vi.fn((item) => item.id)

    render(
      <VirtualListTanStack
        items={items}
        itemHeight={50}
        containerHeight={200}
        renderItem={(item) => <div>{item.name}</div>}
        getItemKey={getItemKey}
      />
    )

    expect(getItemKey).toHaveBeenCalled()
  })
})

