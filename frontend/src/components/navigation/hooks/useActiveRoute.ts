import { useLocation } from 'react-router-dom'

/**
 * Hook to determine if a route is active
 * Supports exact match and prefix matching
 */
export function useActiveRoute(
  path: string,
  exact: boolean = false
): boolean {
  const location = useLocation()

  if (exact) {
    return location.pathname === path
  }

  // Prefix matching - check if current path starts with the given path
  // Also handle root path specially
  if (path === '/') {
    return location.pathname === '/'
  }

  return location.pathname.startsWith(path)
}

/**
 * Hook to get the current active route path
 */
export function useCurrentRoute(): string {
  const location = useLocation()
  return location.pathname
}

