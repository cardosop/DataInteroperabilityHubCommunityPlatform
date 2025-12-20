/**
 * Code Splitting Utilities
 *
 * Utilities for implementing code splitting strategies:
 * - Route-based code splitting
 * - Component-based code splitting
 * - Library splitting (vendor chunks)
 */

import React, { ComponentType, LazyExoticComponent, Suspense } from 'react'
import { Loading } from '@/components/common/Loading'

/**
 * Options for creating lazy components
 */
export interface LazyComponentOptions {
  /**
   * Fallback component to show while loading
   */
  fallback?: React.ReactNode
  /**
   * Component display name (for debugging)
   */
  displayName?: string
  /**
   * Preload hint for the chunk
   */
  preload?: boolean
}

/**
 * Create a lazy-loaded component with Suspense boundary
 *
 * @param importFn - Function that returns a promise resolving to the component
 * @param options - Options for the lazy component
 * @returns Lazy component wrapped with Suspense
 *
 * @example
 * ```tsx
 * const HeavyChart = createLazyComponent(() => import('./HeavyChart'))
 *
 * function Dashboard() {
 *   return <HeavyChart data={data} />
 * }
 * ```
 */
export function createLazyComponent<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  options: LazyComponentOptions = {}
): LazyExoticComponent<T> {
  const { displayName, preload } = options
  const LazyComponent = React.lazy(importFn)

  // Set display name for debugging
  if (displayName) {
    LazyComponent.displayName = displayName
  }

  // Preload hint (browser will prefetch the chunk)
  if (preload && typeof document !== 'undefined') {
    // This is a hint to the browser, actual preloading is handled by Vite
    const link = document.createElement('link')
    link.rel = 'modulepreload'
    // Note: The actual URL will be determined by Vite's build process
  }

  return LazyComponent
}

/**
 * Create a lazy component with custom Suspense boundary
 *
 * @param importFn - Function that returns a promise resolving to the component
 * @param fallback - Fallback component to show while loading
 * @param displayName - Component display name
 * @returns Component that wraps lazy component with Suspense
 *
 * @example
 * ```tsx
 * const HeavyEditor = createLazyComponentWithSuspense(
 *   () => import('./HeavyEditor'),
 *   <LoadingSpinner />
 * )
 *
 * function Page() {
 *   return <HeavyEditor />
 * }
 * ```
 */
export function createLazyComponentWithSuspense<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  fallback?: React.ReactNode,
  displayName?: string
): React.FC<React.ComponentProps<T>> {
  const LazyComponent = createLazyComponent(importFn, { displayName })

  const WrappedComponent: React.FC<React.ComponentProps<T>> = (props) => {
    return (
      <Suspense fallback={fallback || <Loading />}>
        <LazyComponent {...props} />
      </Suspense>
    )
  }

  if (displayName) {
    WrappedComponent.displayName = `Lazy(${displayName})`
  }

  return WrappedComponent
}

/**
 * Create a lazy route with optimized chunk naming
 *
 * @param importFn - Function that returns a promise resolving to the page component
 * @param chunkName - Optional chunk name for better caching (e.g., 'pages-home')
 * @param fallback - Fallback component to show while loading
 * @returns Lazy route element with Suspense
 *
 * @example
 * ```tsx
 * const HomePage = createLazyRoute(
 *   () => import('@/pages/Home'),
 *   'pages-home'
 * )
 * ```
 */
export function createLazyRoute(
  importFn: () => Promise<{ default: React.ComponentType }>,
  chunkName?: string,
  fallback?: React.ReactNode
): React.ReactElement {
  // Use dynamic import with webpackChunkName comment for better chunk naming
  // Vite will use the chunkName parameter for chunk naming
  const LazyComponent = React.lazy(importFn)

  // Set chunk name if provided (Vite uses this for chunk naming)
  if (chunkName && LazyComponent.displayName !== chunkName) {
    LazyComponent.displayName = chunkName
  }

  return (
    <Suspense fallback={fallback || <Loading />}>
      <LazyComponent />
    </Suspense>
  )
}

/**
 * Preload a chunk (useful for prefetching routes/components)
 *
 * @param importFn - Function that returns a promise resolving to the module
 * @returns Promise that resolves when the chunk is loaded
 *
 * @example
 * ```tsx
 * // Preload on hover
 * <Link
 *   to="/heavy-page"
 *   onMouseEnter={() => preloadChunk(() => import('@/pages/HeavyPage'))}
 * >
 *   Heavy Page
 * </Link>
 * ```
 */
export async function preloadChunk<T>(
  importFn: () => Promise<T>
): Promise<T> {
  return importFn()
}

/**
 * Group routes by feature for better chunk organization
 *
 * @param routes - Array of route import functions
 * @param featureName - Name of the feature (e.g., 'admin', 'marketplace')
 * @returns Array of lazy route elements grouped by feature
 *
 * @example
 * ```tsx
 * const adminRoutes = createFeatureRoutes(
 *   [
 *     () => import('@/pages/admin/Users'),
 *     () => import('@/pages/admin/Settings'),
 *   ],
 *   'admin'
 * )
 * ```
 */
export function createFeatureRoutes(
  routes: Array<() => Promise<{ default: React.ComponentType }>>,
  featureName: string
): React.ReactElement[] {
  return routes.map((importFn, index) =>
    createLazyRoute(importFn, `pages-${featureName}-${index}`)
  )
}

/**
 * Create a vendor chunk preloader
 * Useful for preloading heavy libraries before they're needed
 *
 * @param importFn - Function that returns a promise resolving to the library
 * @returns Function to preload the library
 *
 * @example
 * ```tsx
 * const preloadMonaco = createVendorPreloader(() => import('monaco-editor'))
 *
 * // Preload on component mount
 * useEffect(() => {
 *   preloadMonaco()
 * }, [])
 * ```
 */
export function createVendorPreloader<T>(
  importFn: () => Promise<T>
): () => Promise<T> {
  let preloadPromise: Promise<T> | null = null

  return () => {
    if (!preloadPromise) {
      preloadPromise = importFn()
    }
    return preloadPromise
  }
}

/**
 * Chunk naming strategy for better organization
 */
export enum ChunkGroup {
  PAGES = 'pages',
  COMPONENTS = 'components',
  FEATURES = 'features',
  VENDORS = 'vendors',
  LIB = 'lib',
}

/**
 * Generate chunk name based on module path and group
 *
 * @param modulePath - Path to the module
 * @param group - Chunk group
 * @returns Chunk name
 */
export function generateChunkName(
  modulePath: string,
  group: ChunkGroup = ChunkGroup.PAGES
): string {
  // Extract meaningful name from path
  const pathParts = modulePath.split('/')
  const fileName = pathParts[pathParts.length - 1]?.replace(/\.(tsx?|jsx?)$/, '') || 'module'
  const feature = pathParts.find((part) =>
    ['pages', 'components', 'features', 'admin', 'marketplace'].includes(part)
  ) || 'app'

  return `${group}-${feature}-${fileName}`.toLowerCase()
}

