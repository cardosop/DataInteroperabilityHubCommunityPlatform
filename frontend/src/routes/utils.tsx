/**
 * Route Utilities
 *
 * Utility functions for route configuration and rendering.
 */

import React from 'react'
import { Route } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import type { RouteConfig } from './types'

/**
 * Render a route with appropriate guards
 *
 * Uses ProtectedRoute component which handles all guard logic
 * (authentication, permissions, roles) in a unified way.
 */
export function renderRoute(route: RouteConfig, index?: number): React.ReactElement {
  let element = route.element

  // Apply guards using ProtectedRoute if any protection is required
  if (route.requireAuth || route.permissions || route.roles) {
    element = (
      <ProtectedRoute
        requireAuth={route.requireAuth}
        permissions={route.permissions}
        requireAllPermissions={route.requireAllPermissions}
        roles={route.roles}
        redirectTo={route.redirectTo || '/login'}
        unauthorizedRedirectTo={route.redirectTo || '/unauthorized'}
      >
        {element}
      </ProtectedRoute>
    )
  }

  return (
    <Route key={route.path || index} path={route.path} element={element}>
      {route.children?.map((childRoute, childIndex) =>
        renderRoute(childRoute, childIndex)
      )}
    </Route>
  )
}

/**
 * Create a lazy-loaded route element with optimized code splitting
 *
 * Uses Vite's dynamic import with chunk naming for better caching and loading.
 * Routes are automatically split into separate chunks based on their path.
 */
import { Loading } from '@/components/common/Loading'
import { generateChunkName, ChunkGroup } from '@/utils/codeSplitting'

export function createLazyRoute(
  importFn: () => Promise<{ default: React.ComponentType }>,
  chunkName?: string
): React.ReactElement {
  const LazyComponent = React.lazy(() => {
    // Generate chunk name from import function if not provided
    // This helps Vite create better chunk names for route-based code splitting
    const importString = importFn.toString()
    const chunkNameFromImport = chunkName || generateChunkName(importString, ChunkGroup.PAGES)

    // Return the import with chunk name hint
    // Vite will use this for chunk naming in the build
    return importFn().then((module) => {
      // Set display name for debugging
      if (module.default && !module.default.displayName) {
        module.default.displayName = chunkNameFromImport
      }
      return module
    })
  })

  return (
    <React.Suspense fallback={<Loading />}>
      <LazyComponent />
    </React.Suspense>
  )
}

