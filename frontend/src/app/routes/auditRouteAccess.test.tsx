/**
 * Phase 234.2 — `/audit` route access-control drift test.
 *
 * Asserts the frontend `requiredRole` allow-list on the `/audit` and
 * `/audit/:id` routes matches the backend's
 * ``AUDIT_READ_ROLES = ["TENANT_ADMIN", "AUDITOR", "PLATFORM_ADMIN"]``
 * (see ``hub/apps/audit/views.py``). The backend grants TENANT_ADMIN
 * read access to audit events; the frontend was previously more
 * restrictive (only AUDITOR / PLATFORM_ADMIN), creating an explicit
 * UX gap where a tenant admin had the data via API but no UI to view it.
 *
 * Test strategy
 * -------------
 *
 * We walk the exported ``appRoutes`` tree (same source of truth used by
 * production via ``createBrowserRouter``), locate the entries for
 * ``/audit`` and ``/audit/:id``, and introspect the React element wrapped
 * around each. The contract is enforced via ``<ProtectedRoute
 * requiredRole={...}>`` so we read that prop directly — no DOM render,
 * no mocks, no Page-component dependency.
 *
 * Drift surfaces here as either:
 *   * TENANT_ADMIN missing from the allow-list (the gap this phase fixes), or
 *   * Frontend granting a role the backend doesn't (the inverse drift —
 *     would leak an empty 403'd page).
 *
 * Pattern mirrors ``mvpGateDrift.test.tsx`` which already inspects route
 * element trees in the same way.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';

import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { appRoutes } from './routes';

// NOTE on test strategy: this file uses STATIC route-tree introspection
// rather than render-based behavioural tests. Two reasons:
//
//   1. Coverage symmetry. A render-based test for "TENANT_ADMIN passes
//      ProtectedRoute when requiredRole contains TENANT_ADMIN" duplicates
//      the contract of ``ProtectedRoute`` itself, already pinned by 8
//      tests in ``src/shared/components/__tests__/ProtectedRoute.test.tsx``
//      (run via ``npm run test:component:protected-route``). The unique
//      thing about /audit is the SET of roles wired into its
//      ``requiredRole`` prop; the static check below verifies exactly
//      that set, with zero dependence on render-time behaviour.
//
//   2. The render-based approach is currently env-blocked repo-wide
//      (React 19 + @testing-library/react v16 ``React.act`` lookup
//      mismatch affecting EVERY ``render()`` call — same failure mode
//      hits the pre-existing ``odps-redirects.test.tsx``, the
//      ``AdminAuditLogPage.test.tsx``, etc.). Fixing that env issue is
//      a separate test-infra phase. Static introspection sidesteps it
//      while still providing the load-bearing contract proof.
//
// The two layers together — static contract here + behavioural contract
// in ProtectedRoute.test.tsx — transitively prove:
//   "TENANT_ADMIN can access /audit; DATA_PROVIDER cannot."

// Single source of truth — must match
// hub/apps/audit/views.py::AUDIT_READ_ROLES exactly.
const EXPECTED_AUDIT_READ_ROLES = ['TENANT_ADMIN', 'AUDITOR', 'PLATFORM_ADMIN'] as const;

type RouteLike = {
  path?: string;
  index?: boolean;
  element?: React.ReactNode;
  children?: RouteLike[];
};

/** Yield `{ fullPath, element }` for every leaf route in the tree. */
function* walkRoutes(
  routes: RouteLike[],
  parentPath = '',
): Generator<{ fullPath: string; element: React.ReactNode }> {
  for (const route of routes) {
    let here = parentPath;
    if (route.path !== undefined) {
      const seg = route.path.startsWith('/') ? route.path : `/${route.path}`;
      here = parentPath.replace(/\/$/, '') + seg;
    }
    if (route.element !== undefined && route.element !== null) {
      yield { fullPath: here || '/', element: route.element };
    }
    if (route.children) {
      yield* walkRoutes(route.children, here);
    }
  }
}

/** Locate a <ProtectedRoute> element somewhere in this element subtree.
 *
 * Routes layer ``<ErrorBoundary><ProtectedRoute>...</ProtectedRoute></ErrorBoundary>``,
 * occasionally with a ``<CapabilityRoute>`` interlayer. A linear search
 * down children is sufficient because the wrapping order is convention.
 */
function findProtectedRouteElement(
  element: React.ReactNode,
): React.ReactElement | null {
  if (!React.isValidElement(element)) return null;
  if (element.type === ProtectedRoute) return element as React.ReactElement;
  const props = element.props as { children?: React.ReactNode } | undefined;
  const children = props?.children;
  if (children === undefined || children === null) return null;
  const childArray = Array.isArray(children) ? children : [children];
  for (const child of childArray) {
    const hit = findProtectedRouteElement(child as React.ReactNode);
    if (hit) return hit;
  }
  return null;
}

describe('/audit route access control (Phase 234.2)', () => {
  const routeEntries: Record<string, React.ReactNode> = {};
  for (const entry of walkRoutes(appRoutes as RouteLike[])) {
    routeEntries[entry.fullPath] = entry.element;
  }

  it.each(['/audit', '/audit/:id'])(
    '%s is wrapped by <ProtectedRoute>',
    (path) => {
      const element = routeEntries[path];
      expect(
        element,
        `route ${path} not found in appRoutes — has it been moved or renamed?`,
      ).toBeDefined();
      const guard = findProtectedRouteElement(element);
      expect(
        guard,
        `route ${path} is missing a <ProtectedRoute> wrapper`,
      ).not.toBeNull();
    },
  );

  it.each(['/audit', '/audit/:id'])(
    '%s requiredRole includes TENANT_ADMIN (matches backend AUDIT_READ_ROLES)',
    (path) => {
      const guard = findProtectedRouteElement(routeEntries[path])!;
      const required = (
        guard.props as { requiredRole?: string[] }
      ).requiredRole;
      expect(required, `route ${path} has no requiredRole prop`).toBeDefined();
      expect(required).toContain('TENANT_ADMIN');
    },
  );

  it.each(['/audit', '/audit/:id'])(
    '%s requiredRole exactly matches backend AUDIT_READ_ROLES (no drift either direction)',
    (path) => {
      const guard = findProtectedRouteElement(routeEntries[path])!;
      const required = (
        guard.props as { requiredRole?: string[] }
      ).requiredRole;
      // Set comparison so the order in routes.tsx can differ from the
      // Python literal without breaking the test — the contract is the
      // SET of allowed roles.
      expect(new Set(required)).toEqual(new Set(EXPECTED_AUDIT_READ_ROLES));
    },
  );

  it('DATA_PROVIDER is NOT in /audit allow-list (regression guard)', () => {
    const guard = findProtectedRouteElement(routeEntries['/audit'])!;
    const required = (
      guard.props as { requiredRole?: string[] }
    ).requiredRole;
    expect(required).not.toContain('DATA_PROVIDER');
    expect(required).not.toContain('DATA_CONSUMER');
    expect(required).not.toContain('USER');
  });
});

// ---------------------------------------------------------------------------
// Sidebar ↔ route drift guard (Phase 234.2 audit-fix gap)
// ---------------------------------------------------------------------------
//
// The original 234.2 fix closed the FE/BE allow-list drift on the /audit
// route. A second drift surface remained: ``SIDEBAR_NAV_ITEMS`` in
// ``frontend/src/features/shell/utils/navItems.ts`` declares its OWN
// ``requiredRole`` to decide whether to render the link. If the sidebar
// allows a role the route rejects, that role's users see a sidebar link
// that redirects to /403 on click — the exact UX bug 234.2 was filed to
// fix, mirrored on the other config surface. Pre-234.2 this was real:
// the sidebar entry already included ``TENANT_ADMIN`` but the route did
// not.
//
// This guard pins the contract: for every nav item that points at /audit,
// every role in its ``requiredRole`` MUST also be in the route's
// ``requiredRole``. The reverse direction (route accepts more than the
// sidebar shows) is allowed — sometimes a route is reachable only via
// deep-link, and that's intentional. The strict-subset check fails the
// build the moment the same drift class is re-introduced from either
// file.

import { SIDEBAR_NAV_ITEMS, type NavItem } from '../../features/shell/utils/navItems';

describe('/audit sidebar ↔ route alignment (Phase 234.2 audit-fix)', () => {
  function* walkNav(items: readonly NavItem[]): Generator<NavItem> {
    for (const item of items) {
      yield item;
      if (item.children) yield* walkNav(item.children);
    }
  }

  function getRouteRequiredRole(path: string): string[] {
    for (const entry of walkRoutes(appRoutes as RouteLike[])) {
      if (entry.fullPath === path) {
        const guard = findProtectedRouteElement(entry.element);
        if (guard) {
          return (
            (guard.props as { requiredRole?: string[] }).requiredRole ?? []
          );
        }
      }
    }
    throw new Error(`route ${path} not found in appRoutes`);
  }

  function findNavItem(path: string): NavItem | undefined {
    for (const item of walkNav(SIDEBAR_NAV_ITEMS)) {
      if (item.path === path) return item;
    }
    return undefined;
  }

  it('every role allowed by the /audit nav item is also allowed by the /audit route', () => {
    const navItem = findNavItem('/audit');
    expect(
      navItem,
      '/audit nav entry not found in SIDEBAR_NAV_ITEMS — has it been renamed?',
    ).toBeDefined();

    const navRoles = new Set(navItem!.requiredRole ?? []);
    const routeRoles = new Set(getRouteRequiredRole('/audit'));

    // For every role the sidebar exposes the link to, the route MUST
    // accept it — otherwise the click leads to /403.
    const navOnly = [...navRoles].filter((r) => !routeRoles.has(r));
    expect(
      navOnly,
      `sidebar exposes /audit to ${JSON.stringify(navOnly)} but the route rejects ` +
        `them (would redirect to /403). Either add the role to the route's ` +
        `ProtectedRoute requiredRole in routes.tsx, or remove it from the nav ` +
        `item's requiredRole in navItems.ts.`,
    ).toEqual([]);
  });

  it('TENANT_ADMIN is in BOTH the nav item AND the route (the 234.2 contract anchor)', () => {
    // Direct positive assertion of the 234.2 contract at both surfaces.
    // The previous test catches drift; this one anchors the fixed state
    // so a downgrade from EITHER file fails the build immediately.
    const navItem = findNavItem('/audit');
    expect(navItem?.requiredRole).toContain('TENANT_ADMIN');
    expect(getRouteRequiredRole('/audit')).toContain('TENANT_ADMIN');
  });
});
