/**
 * close-test-coverage-gaps 3.0 — the /signup route contract.
 *
 * Checkpoint outcome: backend org creation is PLATFORM_ADMIN-only on every
 * surface (POST /api/v1/admin/tenants/ — IsAuthenticated + IsPlatformAdmin;
 * POST /api/v1/tenants/ — same; POST /api/v1/tenants/onboarding/ — same,
 * after the layer-coherence fix this checkpoint shipped). Per design D6 a
 * public self-service /signup that 403s on submit must NOT exist — the route
 * is instead the PLATFORM_ADMIN tenant-provisioning page behind a
 * ProtectedRoute role guard.
 *
 * Static tree introspection (the auditRouteAccess pattern — render-based
 * tests are env-blocked repo-wide). Pins:
 *
 * - a top-level `/signup` route exists (public URL, kept stable for
 *   external links — the guard redirects, it does not 404);
 * - its element is wrapped in ProtectedRoute with
 *   requiredRole=['PLATFORM_ADMIN'] (unauthenticated → /login,
 *   authenticated non-admin → /403);
 * - it renders TenantSignupPage inside the guard;
 * - it carries NO CapabilityRoute (the backend is the enforcement point —
 *   no runtime capability keys exist for org creation) and NO
 *   MvpGatedRoute (top-level public-path table entry, not an MVP-gated
 *   surface).
 */

import React from 'react';
import { describe, expect, it } from 'vitest';

import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
import { MvpGatedRoute } from '../../shared/components/MvpGatedRoute';
import { TenantSignupPage } from '../../features/onboarding/components/TenantSignupPage';
import { appRoutes } from './routes';

type RouteLike = {
  path?: string;
  index?: boolean;
  element?: React.ReactNode;
  children?: RouteLike[];
};

/** Locate the first element of the given type in a subtree (the
 * wrapping order is convention — linear search suffices). */
function findElementOfType(
  element: React.ReactNode,
  type: React.ElementType,
): React.ReactElement | null {
  if (!React.isValidElement(element)) return null;
  if (element.type === type) return element as React.ReactElement;
  const props = element.props as { children?: React.ReactNode } | undefined;
  const children = props?.children;
  if (children === undefined || children === null) return null;
  const childArray = Array.isArray(children) ? children : [children];
  for (const child of childArray) {
    const hit = findElementOfType(child as React.ReactNode, type);
    if (hit) return hit;
  }
  return null;
}

describe('/signup route (close-test-coverage-gaps 3.0)', () => {
  function findRoute(
    routes: RouteLike[],
    path: string,
  ): RouteLike | undefined {
    for (const route of routes) {
      if (route.path === path) return route;
      if (route.children) {
        const hit = findRoute(route.children as RouteLike[], path);
        if (hit) return hit;
      }
    }
    return undefined;
  }

  const signup = findRoute(appRoutes as unknown as RouteLike[], '/signup');

  it('defines a top-level /signup route', () => {
    expect(
      signup,
      '/signup route missing from appRoutes — close-test-coverage-gaps 3.0 wiring',
    ).toBeDefined();
    expect(signup?.element).toBeDefined();
  });

  it('sits in the top-level (pre-shell) section, before the / RootRoute', () => {
    const topLevel = (appRoutes as unknown as RouteLike[]);
    const signupIndex = topLevel.findIndex((route) => route.path === '/signup');
    const rootIndex = topLevel.findIndex((route) => route.path === '/');
    expect(signupIndex).toBeGreaterThanOrEqual(0);
    expect(rootIndex).toBeGreaterThanOrEqual(0);
    expect(signupIndex).toBeLessThan(rootIndex);
  });

  it('is PLATFORM_ADMIN-gated via ProtectedRoute', () => {
    const guard = findElementOfType(signup?.element, ProtectedRoute);
    expect(
      guard,
      '/signup must be wrapped in ProtectedRoute (org creation is PLATFORM_ADMIN-only — design D6)',
    ).not.toBeNull();
    const requiredRole = (guard?.props as { requiredRole?: string[] } | undefined)?.requiredRole;
    expect(requiredRole).toContain('PLATFORM_ADMIN');
  });

  it('renders TenantSignupPage inside the guard', () => {
    expect(findElementOfType(signup?.element, TenantSignupPage)).not.toBeNull();
  });

  it('carries no CapabilityRoute and no MvpGatedRoute', () => {
    expect(findElementOfType(signup?.element, CapabilityRoute)).toBeNull();
    expect(findElementOfType(signup?.element, MvpGatedRoute)).toBeNull();
  });
});
