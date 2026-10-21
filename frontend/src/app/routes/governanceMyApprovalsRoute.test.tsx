/**
 * close-test-coverage-gaps 2.1 — the /governance/my-approvals route contract.
 *
 * Static tree introspection (the auditRouteAccess pattern — render-based
 * tests are env-blocked repo-wide; see that file's NOTE). Pins:
 *
 * - the `my-approvals` child exists under the /governance subtree;
 * - it sits IMMEDIATELY AFTER `processor-agreements` (the task placement);
 * - it carries NO ProtectedRoute of its own (the role is INHERITED from
 *   the /governance parent guard) and NO CapabilityRoute (the 278.I.1
 *   inbox has no runtime capability of its own — the backend gates the
 *   surface, and the inbox aggregates items the role can already see);
 * - the routes source lazy-imports MyApprovalsInbox (the lazy-load
 *   requirement, same single-source discipline as the siblings).
 */

import React from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
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

// vitest runs with cwd = frontend package root — resolve the module
// source path from the working directory (import.meta.url is not a
// file:// URL under this jsdom setup).
const ROUTES_SOURCE = resolve(process.cwd(), 'src/app/routes/routes.tsx');

describe('/governance/my-approvals route (close-test-coverage-gaps 2.1)', () => {
  // appRoutes nests under a root route object — walk the tree (the
  // auditRouteAccess pattern) instead of a flat find.
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

  const governance = findRoute(appRoutes as unknown as RouteLike[], 'governance');
  expect(
    governance,
    '/governance subtree not found in appRoutes — has it been moved?',
  ).toBeDefined();

  const children = (governance?.children ?? []) as RouteLike[];
  const myApprovals = children.find((route) => route.path === 'my-approvals');
  const processorAgreements = children.find(
    (route) => route.path === 'processor-agreements',
  );

  it('defines the my-approvals child under /governance', () => {
    expect(
      myApprovals,
      'my-approvals route missing from the /governance subtree — close-test-coverage-gaps 2.1',
    ).toBeDefined();
    expect(myApprovals?.element).toBeDefined();
  });

  it('places my-approvals immediately after processor-agreements', () => {
    const myIndex = children.indexOf(myApprovals as RouteLike);
    const processorIndex = children.indexOf(processorAgreements as RouteLike);
    expect(myIndex).toBeGreaterThanOrEqual(0);
    expect(processorIndex).toBeGreaterThanOrEqual(0);
    expect(myIndex).toBe(processorIndex + 1);
  });

  it('inherits the role from the /governance parent guard (no own ProtectedRoute)', () => {
    expect(findElementOfType(myApprovals?.element, ProtectedRoute)).toBeNull();
    // the parent guard is the inheritance source — pin it still exists
    expect(findElementOfType(governance?.element, ProtectedRoute)).not.toBeNull();
  });

  it('carries no CapabilityRoute of its own', () => {
    expect(findElementOfType(myApprovals?.element, CapabilityRoute)).toBeNull();
  });

  it('lazy-imports MyApprovalsInbox in routes.tsx', () => {
    const source = readFileSync(ROUTES_SOURCE, 'utf-8');
    expect(source).toContain(
      "import('../../features/governance/components/MyApprovalsInbox')",
    );
  });
});
