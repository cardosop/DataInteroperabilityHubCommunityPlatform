/**
 * Track A PR 4 — drift test for the MVP gate convention.
 *
 * Asserts the three-layer convention from docs/mvp-gate.md is consistent:
 *
 *   Forward drift: every path in NON_MVP_PATHS has <MvpGatedRoute> as the
 *   outermost element wrapper in its routes.tsx entry. Catches the case
 *   where a developer adds a path to NON_MVP_PATHS but forgets to wrap
 *   the route — sidebar hides it, but typing the URL still loads it.
 *
 *   Inverse drift: every route wrapped in <MvpGatedRoute> has its full
 *   path (or a covering parent prefix) in NON_MVP_PATHS. Catches the
 *   case where someone wraps a route but forgets to add it to
 *   NON_MVP_PATHS — the sidebar still shows the link, leading to a
 *   confusing dead-link UX.
 *
 * The test walks the exported `appRoutes` array (a pure JS structure)
 * and inspects each route's React element type. We require <MvpGatedRoute>
 * to be the *outermost* component (above ErrorBoundary, CapabilityRoute,
 * etc.) so wrapping order is deterministic and the gate fires before
 * any expensive child renders.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';

import { NON_MVP_PATHS } from '../../features/shell/utils/mvpNav';
import { MvpGatedRoute } from '../../shared/components/MvpGatedRoute';
import { appRoutes } from './routes';

type RouteLike = {
  path?: string;
  index?: boolean;
  element?: React.ReactNode;
  children?: RouteLike[];
};

/**
 * Walk the route config and emit `{ fullPath, element }` for each route.
 * Joins parent paths so '/integrations' + 'connections' becomes
 * '/integrations/connections'. Index routes inherit their parent's path.
 */
function* walkRoutes(
  routes: RouteLike[],
  parentPath = '',
): Generator<{ fullPath: string; element: React.ReactNode }> {
  for (const route of routes) {
    let here = parentPath;
    if (route.path !== undefined) {
      const seg = route.path.startsWith('/') ? route.path : `/${route.path}`;
      // Avoid double slashes when parent is '/'
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

/** True if a path matches NON_MVP_PATHS exactly OR has an ancestor in it. */
function isPathOrAncestorInNonMvp(path: string): boolean {
  if (NON_MVP_PATHS.has(path)) return true;
  // Walk up the segments: '/mesh/topology' → check '/mesh'.
  const segments = path.split('/').filter(Boolean);
  for (let i = segments.length - 1; i > 0; i--) {
    const ancestor = '/' + segments.slice(0, i).join('/');
    if (NON_MVP_PATHS.has(ancestor)) return true;
  }
  // Prefix matches (mirror of MVP_PREFIX_PATHS = ['/ai/'])
  if (path.startsWith('/ai/')) return true;
  return false;
}

/** True if the React element's outermost component is <MvpGatedRoute>. */
function isOutermostMvpGated(element: React.ReactNode): boolean {
  if (!React.isValidElement(element)) return false;
  return element.type === MvpGatedRoute;
}

describe('MVP gate drift — routes.tsx ↔ NON_MVP_PATHS consistency', () => {
  // Build the inventory once.
  const allRoutes = Array.from(walkRoutes(appRoutes as RouteLike[]));

  it('every NON_MVP_PATHS entry has at least one route', () => {
    // Sanity: a typo in NON_MVP_PATHS would let it pass the drift test
    // silently (no route → no missing wrapper). Force every entry to
    // resolve to a real route, exact match.
    const allPaths = new Set(allRoutes.map((r) => r.fullPath));
    const missing: string[] = [];
    for (const p of NON_MVP_PATHS) {
      if (!allPaths.has(p)) missing.push(p);
    }
    expect(
      missing,
      `NON_MVP_PATHS contains paths with no route in routes.tsx: ${JSON.stringify(missing)}. ` +
        `Either fix the typo in NON_MVP_PATHS, or add a route for the path.`,
    ).toEqual([]);
  });

  it('forward drift: every NON_MVP_PATHS route has <MvpGatedRoute> as outermost wrapper', () => {
    const failures: string[] = [];
    for (const { fullPath, element } of allRoutes) {
      if (!NON_MVP_PATHS.has(fullPath)) continue;
      if (!isOutermostMvpGated(element)) {
        failures.push(fullPath);
      }
    }
    expect(
      failures,
      `Routes in NON_MVP_PATHS missing <MvpGatedRoute> as the outermost element: ` +
        `${JSON.stringify(failures)}. Wrap the route's element with ` +
        `<MvpGatedRoute>...</MvpGatedRoute>.`,
    ).toEqual([]);
  });

  it('inverse drift: every <MvpGatedRoute>-wrapped route has its path covered by NON_MVP_PATHS', () => {
    const dead: string[] = [];
    for (const { fullPath, element } of allRoutes) {
      if (!isOutermostMvpGated(element)) continue;
      // Allow exact match OR ancestor-in-NON_MVP_PATHS OR /ai/* prefix.
      if (!isPathOrAncestorInNonMvp(fullPath)) {
        dead.push(fullPath);
      }
    }
    expect(
      dead,
      `Routes wrapped in <MvpGatedRoute> but not covered by NON_MVP_PATHS ` +
        `(dead gates that confuse the sidebar): ${JSON.stringify(dead)}. ` +
        `Either add the path to NON_MVP_PATHS in mvpNav.ts, or remove the wrapper.`,
    ).toEqual([]);
  });

  it('/semantic is NEVER wrapped in <MvpGatedRoute> (permanent MVP scope)', () => {
    // Documented exception (see docs/mvp-gate.md). Catch the case where
    // a future refactor accidentally bundles /semantic with the
    // non-MVP routes.
    const semanticRoutes = allRoutes.filter((r) => r.fullPath === '/semantic');
    expect(
      semanticRoutes.length,
      'Expected exactly one /semantic route in routes.tsx',
    ).toBe(1);
    expect(
      isOutermostMvpGated(semanticRoutes[0].element),
      '/semantic must NOT be wrapped in <MvpGatedRoute> (MVP-scope per ' +
        'docs/mvp-gate.md "Permanent exception" section)',
    ).toBe(false);
  });
});
