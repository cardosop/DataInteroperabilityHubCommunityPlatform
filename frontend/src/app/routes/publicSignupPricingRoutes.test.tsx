/**
 * close-test-coverage-gaps 3.1 — the public /pricing route and the
 * authenticated /product-tour route.
 *
 * SCOPE NOTE (the 3.0 checkpoint outcome, user decision): /signup was
 * wired ADMIN-GATED by the 3.0 session — `ProtectedRoute
 * requiredRole={['PLATFORM_ADMIN']}` around the reworked TenantSignupPage
 * (org creation is PLATFORM_ADMIN-only across admin/tenants/,
 * /api/v1/tenants/, and /api/v1/tenants/onboarding/). This file pins the
 * REMAINING 3.1 surfaces only; the signup contract is pinned by that
 * session's signupRoute.test.tsx.
 *
 * Static tree introspection (the auditRouteAccess pattern — render-based
 * tests are env-blocked repo-wide). Pins:
 *
 * - /pricing is a TOP-LEVEL public route (sibling of /login, NOT a child
 *   of RootRoute) carrying NO ProtectedRoute wrapper;
 * - /product-tour is a dedicated AUTHENTICATED route: a child of the
 *   RootRoute subtree (inherits the authenticated shell), and the
 *   ProductTourGate is NOT mounted on the HomePage (auto-mount
 *   regression guard — the gate renders an overlay only on its own
 *   route);
 * - both components are lazy-imported in routes.tsx.
 */

import React from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { RootRoute } from './RootRoute';
import { appRoutes } from './routes';

// vitest runs with cwd = frontend package root (import.meta.url is not a
// file:// URL under this jsdom setup — the 2.1 pin learned this the hard way).
const ROUTES_SOURCE = resolve(process.cwd(), 'src/app/routes/routes.tsx');
const HOME_PAGE_SOURCE = resolve(process.cwd(), 'src/app/pages/HomePage.tsx');

type RouteLike = {
  path?: string;
  index?: boolean;
  element?: React.ReactNode;
  children?: RouteLike[];
};

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

const topLevel = appRoutes as unknown as RouteLike[];

describe('/pricing public route (close-test-coverage-gaps 3.1)', () => {
  it('is a top-level public route with no ProtectedRoute', () => {
    const route = topLevel.find((r) => r.path === '/pricing');
    expect(
      route,
      '/pricing missing from the top-level appRoutes — close-test-coverage-gaps 3.1',
    ).toBeDefined();
    expect(route?.element).toBeDefined();
    expect(findElementOfType(route?.element, ProtectedRoute)).toBeNull();
  });

  it('lazy-imports PricingPage', () => {
    const source = readFileSync(ROUTES_SOURCE, 'utf-8');
    expect(source).toContain("import('../../features/pricing/PricingPage')");
  });
});

describe('/product-tour authenticated route (close-test-coverage-gaps 3.1)', () => {
  it('is a child of the RootRoute subtree (authenticated shell)', () => {
    const root = topLevel.find((r) => r.element !== undefined && r.element.type === RootRoute);
    expect(root, 'RootRoute top-level entry missing').toBeDefined();
    const children = (root?.children ?? []) as RouteLike[];
    const tour = children.find((r) => r.path === 'product-tour');
    expect(
      tour,
      'product-tour missing from the RootRoute children — close-test-coverage-gaps 3.1',
    ).toBeDefined();
    expect(tour?.element).toBeDefined();
  });

  it('is NOT auto-mounted on the HomePage', () => {
    const homeSource = readFileSync(HOME_PAGE_SOURCE, 'utf-8');
    expect(homeSource).not.toContain('ProductTourGate');
    expect(homeSource).not.toContain('ProductTour');
  });

  it('lazy-imports ProductTourGate in routes.tsx', () => {
    const source = readFileSync(ROUTES_SOURCE, 'utf-8');
    expect(source).toContain(
      "import('../../features/onboarding/components/ProductTourGate')",
    );
  });
});
