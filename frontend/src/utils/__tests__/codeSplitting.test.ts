/**
 * Code Splitting Utilities Tests
 *
 * Comprehensive tests for code splitting utilities.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen } from '@testing-library/react'
import {
  createLazyComponent,
  createLazyComponentWithSuspense,
  createLazyRoute,
  preloadChunk,
  createFeatureRoutes,
  createVendorPreloader,
  generateChunkName,
  ChunkGroup,
} from '../codeSplitting'

// Mock component for testing
const MockComponent: React.FC<{ title?: string }> = ({ title = 'Test' }) => (
  <div>{title}</div>
)

describe('codeSplitting utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('createLazyComponent', () => {
    it('should create a lazy component', async () => {
      const importFn = vi.fn(() =>
        Promise.resolve({ default: MockComponent })
      )
      const LazyComponent = createLazyComponent(importFn)

      expect(LazyComponent).toBeDefined()
      expect(importFn).not.toHaveBeenCalled() // Lazy components don't load until rendered
    })

    it('should set display name when provided', () => {
      const importFn = () => Promise.resolve({ default: MockComponent })
      const LazyComponent = createLazyComponent(importFn, {
        displayName: 'TestComponent',
      })

      expect(LazyComponent.displayName).toBe('TestComponent')
    })
  })

  describe('createLazyComponentWithSuspense', () => {
    it('should create a lazy component with Suspense boundary', async () => {
      const importFn = vi.fn(() =>
        Promise.resolve({ default: MockComponent })
      )
      const LazyComponent = createLazyComponentWithSuspense(importFn)

      render(<LazyComponent />)

      // Component should load and render
      await screen.findByText('Test')
      expect(importFn).toHaveBeenCalled()
    })

    it('should use custom fallback', () => {
      const importFn = () => Promise.resolve({ default: MockComponent })
      const fallback = <div>Loading...</div>
      const LazyComponent = createLazyComponentWithSuspense(
        importFn,
        fallback
      )

      const { container } = render(<LazyComponent />)
      // Fallback should be shown initially
      expect(container.textContent).toContain('Loading')
    })
  })

  describe('createLazyRoute', () => {
    it('should create a lazy route element', () => {
      const importFn = () => Promise.resolve({ default: MockComponent })
      const routeElement = createLazyRoute(importFn)

      expect(routeElement).toBeDefined()
      expect(routeElement.type).toBe(React.Suspense)
    })

    it('should use chunk name when provided', () => {
      const importFn = () => Promise.resolve({ default: MockComponent })
      const routeElement = createLazyRoute(importFn, 'pages-home')

      expect(routeElement).toBeDefined()
    })
  })

  describe('preloadChunk', () => {
    it('should preload a chunk', async () => {
      const importFn = vi.fn(() => Promise.resolve({ default: MockComponent }))

      await preloadChunk(importFn)

      expect(importFn).toHaveBeenCalled()
    })
  })

  describe('createFeatureRoutes', () => {
    it('should create feature routes', () => {
      const routes = [
        () => Promise.resolve({ default: MockComponent }),
        () => Promise.resolve({ default: MockComponent }),
      ]
      const featureRoutes = createFeatureRoutes(routes, 'admin')

      expect(featureRoutes).toHaveLength(2)
      expect(featureRoutes[0]).toBeDefined()
      expect(featureRoutes[1]).toBeDefined()
    })
  })

  describe('createVendorPreloader', () => {
    it('should create a vendor preloader', async () => {
      const importFn = vi.fn(() => Promise.resolve({ module: 'test' }))
      const preloader = createVendorPreloader(importFn)

      // First call should trigger import
      await preloader()
      expect(importFn).toHaveBeenCalledTimes(1)

      // Second call should use cached promise
      await preloader()
      expect(importFn).toHaveBeenCalledTimes(1)
    })
  })

  describe('generateChunkName', () => {
    it('should generate chunk name from module path', () => {
      const chunkName = generateChunkName(
        '/src/pages/admin/Users.tsx',
        ChunkGroup.PAGES
      )
      expect(chunkName).toContain('pages')
      expect(chunkName).toContain('admin')
    })

    it('should use default group if not provided', () => {
      const chunkName = generateChunkName('/src/pages/Home.tsx')
      expect(chunkName).toContain('pages')
    })

    it('should handle different chunk groups', () => {
      const componentName = generateChunkName(
        '/src/components/HeavyChart.tsx',
        ChunkGroup.COMPONENTS
      )
      expect(componentName).toContain('components')
    })
  })
})

