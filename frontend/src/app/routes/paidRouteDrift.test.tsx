/**
 * 313.H.4.2 — paid-route capability gating drift test.
 *
 * Four drift directions, all derived from the single source of truth
 * (paidRouteGating.ts + the capability registry):
 *
 *   Forward drift: every route under a paid prefix has an ancestor
 *   <CapabilityRoute> whose capability prop equals the mapped key.
 *   Catches "added a paid route but forgot the wrapper" — in core-only
 *   deployments the page would render against an absent API.
 *
 *   Inverse drift: every <CapabilityRoute> key used in routes.tsx (and
 *   every requiredCapability in the sidebar nav) exists in the
 *   capability registry. Catches "wrapped with a key the service never
 *   registers" — the route would silently 404-redirect forever.
 *
 *   Nav drift: a nav item pointing at a paid prefix must carry the
 *   mapped requiredCapability — catches "sidebar shows a link that
 *   core-only can never serve".
 *
 *   Derivation coverage: every registry definition must actually
 *   derive available=true from its own sample paths — catches a dead
 *   predicate (e.g. a path string typo) that would silently disable
 *   the capability in FULL mode.
 *
 * No mocks: the tests walk the real appRoutes export, the real
 * SIDEBAR_NAV_ITEMS, and run the real deriveCapabilitiesFromOpenAPI
 * over synthetic schemas built from each definition's sample paths.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';

import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
import {
  ALL_CAPABILITY_KEYS,
  CAPABILITY_DEFINITIONS,
  deriveCapabilitiesFromOpenAPI,
} from '../../features/capabilities/services/capabilitiesService';
import { SIDEBAR_NAV_ITEMS } from '../../features/shell/utils/navItems';
import { appRoutes } from './routes';
import {
  isPathUnderPaidPrefix,
  paidCapabilityForPath,
  PAID_ROUTE_CAPABILITIES,
} from './paidRouteGating';

type RouteLike = {
  path?: string;
  index?: boolean;
  element?: React.ReactNode;
  children?: RouteLike[];
};

interface WalkedRoute {
  fullPath: string;
  element: React.ReactNode;
  /** Outermost-first element chain from the tree root to this route. */
  ancestors: React.ReactNode[];
}

function* walkRoutes(
  routes: RouteLike[],
  parentPath = '',
  parentAncestors: React.ReactNode[] = [],
): Generator<WalkedRoute> {
  for (const route of routes) {
    let here = parentPath;
    if (route.path !== undefined) {
      const seg = route.path.startsWith('/') ? route.path : `/${route.path}`;
      here = parentPath.replace(/\/$/, '') + seg;
    }
    const ancestors = route.element !== undefined && route.element !== null
      ? [...parentAncestors, route.element]
      : parentAncestors;
    if (route.element !== undefined && route.element !== null) {
      yield { fullPath: here || '/', element: route.element, ancestors };
    }
    if (route.children) {
      yield* walkRoutes(route.children, here, ancestors);
    }
  }
}

function capabilityKeyOf(element: React.ReactNode): string | undefined {
  if (!React.isValidElement(element)) return undefined;
  if (element.type !== CapabilityRoute) return undefined;
  const props = element.props as { capability?: string };
  return props.capability;
}

/**
 * Collect capability keys from a React ELEMENT TREE (not just the route
 * tree): <CapabilityRoute> is usually nested inside <EB>, <ProtectedRoute>,
 * or <MvpGatedRoute> JSX, so the walk must descend into props.children.
 */
function capabilityKeysInElementTree(element: React.ReactNode): string[] {
  const keys: string[] = [];
  const visit = (node: React.ReactNode): void => {
    const own = capabilityKeyOf(node);
    if (own !== undefined) keys.push(own);
    if (React.isValidElement(node)) {
      const children = (node.props as { children?: React.ReactNode }).children;
      React.Children.forEach(children, visit);
    }
  };
  visit(element);
  return keys;
}

function* walkNavItems(
  items: typeof SIDEBAR_NAV_ITEMS,
): Generator<{ path: string; requiredCapability?: string }> {
  for (const item of items) {
    yield { path: item.path, requiredCapability: item.requiredCapability };
    if (item.children) yield* walkNavItems(item.children);
  }
}

/**
 * Tenant-flag-gated routes (NOT paid — core-app features behind the
 * per-tenant opt-in flags from GET /capabilities/). Same wrapper
 * convention as the paid map; pinned here so a future refactor that
 * drops a wrapper fails loudly (313.H.4 review: consent/ropa/dsar were
 * unwrapped while their dpia/breach/processor siblings were gated).
 */
const TENANT_FLAG_ROUTE_CAPABILITIES: Readonly<Record<string, string>> = {
  '/settings/ropa': 'compliance_ropa',
  '/governance/consent/purposes': 'compliance_consent',
  '/governance/consent/dashboard': 'compliance_consent',
  '/governance/dsar-requests': 'compliance_dsar',
  '/governance/dsar-requests/:id': 'compliance_dsar',
  '/governance/dpia/review-queue': 'compliance_dpia',
  '/governance/dpia/:dpiaId/review': 'compliance_dpia',
  '/governance/dpia/:dpiaId': 'compliance_dpia',
  '/governance/breach': 'compliance_breach',
  '/governance/breach/report': 'compliance_breach',
  '/governance/breach/templates': 'compliance_breach',
  '/governance/breach/:id': 'compliance_breach',
  '/governance/processor-agreements': 'compliance_processor_agreements',
  '/governance/retention/dashboard': 'compliance_retention_enforcer',
};

function tenantFlagCapabilityForPath(path: string): string | undefined {
  return TENANT_FLAG_ROUTE_CAPABILITIES[path];
}

describe('paid-route capability gating — routes.tsx ↔ paidRouteGating ↔ capability registry', () => {
  const allRoutes = Array.from(walkRoutes(appRoutes as RouteLike[]));

  it('every paid prefix has at least one route', () => {
    // A typo in PAID_ROUTE_CAPABILITIES would otherwise pass the drift
    // test silently (no route → no missing wrapper). Force every prefix
    // to resolve to a real route.
    const allPaths = new Set(allRoutes.map((r) => r.fullPath));
    const missing = Object.keys(PAID_ROUTE_CAPABILITIES).filter((p) => !allPaths.has(p));
    expect(
      missing,
      `PAID_ROUTE_CAPABILITIES contains prefixes with no route in routes.tsx: ` +
        `${JSON.stringify(missing)}. Fix the typo or remove the entry.`,
    ).toEqual([]);
  });

  it('forward drift: every route under a paid prefix has the mapped CapabilityRoute wrapper', () => {
    const failures: string[] = [];
    for (const { fullPath, ancestors } of allRoutes) {
      if (!isPathUnderPaidPrefix(fullPath)) continue;
      const expected = paidCapabilityForPath(fullPath);
      if (!expected) continue;
      const keys = ancestors.flatMap(capabilityKeysInElementTree);
      if (!keys.includes(expected)) {
        failures.push(`${fullPath} (expected capability="${expected}", found [${keys.join(', ')}])`);
      }
    }
    expect(
      failures,
      `Paid routes missing <CapabilityRoute capability="..."> with the mapped key: ` +
        `${JSON.stringify(failures, null, 2)}. Wrap the route (or a covering parent) ` +
        `with <CapabilityRoute capability={PAID_ROUTE_CAPABILITIES[...]}> (see paidRouteGating.ts).`,
    ).toEqual([]);
  });

  it('forward drift: every tenant-flag-gated route has the mapped CapabilityRoute wrapper', () => {
    const failures: string[] = [];
    for (const { fullPath, ancestors } of allRoutes) {
      const expected = tenantFlagCapabilityForPath(fullPath);
      if (!expected) continue;
      const keys = ancestors.flatMap(capabilityKeysInElementTree);
      if (!keys.includes(expected)) {
        failures.push(`${fullPath} (expected capability="${expected}", found [${keys.join(', ')}])`);
      }
    }
    expect(
      failures,
      `Tenant-flag routes missing <CapabilityRoute capability="...">: ` +
        `${JSON.stringify(failures, null, 2)}. Wrap them like their dpia/breach siblings.`,
    ).toEqual([]);
  });

  it('capability-key enumeration: every key used in routes.tsx is registered', () => {
    const used = new Set<string>();
    for (const { ancestors } of allRoutes) {
      for (const key of ancestors.flatMap(capabilityKeysInElementTree)) used.add(key);
    }
    const unregistered = [...used].filter((k) => !ALL_CAPABILITY_KEYS.has(k));
    expect(
      unregistered,
      `CapabilityRoute keys not in the capability registry: ${JSON.stringify(unregistered)}. ` +
        `Register them in CAPABILITY_DEFINITIONS (path-derived) or RUNTIME_CAPABILITY_KEYS ` +
        `(capabilitiesService.ts) — an unregistered key silently redirects every visitor.`,
    ).toEqual([]);
  });

  it('capability-key enumeration: every nav requiredCapability is registered', () => {
    const unregistered = Array.from(walkNavItems(SIDEBAR_NAV_ITEMS))
      .map((n) => n.requiredCapability)
      .filter((k): k is string => k !== undefined && !ALL_CAPABILITY_KEYS.has(k));
    expect(
      unregistered,
      `Nav-item capabilities not in the capability registry: ${JSON.stringify(unregistered)}.`,
    ).toEqual([]);
  });

  it('nav drift: nav items pointing at paid prefixes carry the mapped requiredCapability', () => {
    const failures: string[] = [];
    for (const { path, requiredCapability } of walkNavItems(SIDEBAR_NAV_ITEMS)) {
      const expected = paidCapabilityForPath(path);
      if (!expected) continue;
      if (requiredCapability !== expected) {
        failures.push(`${path} (expected requiredCapability="${expected}", found "${requiredCapability ?? ''}")`);
      }
    }
    expect(
      failures,
      `Nav items for paid destinations missing the mapped requiredCapability: ` +
        `${JSON.stringify(failures, null, 2)}. Add requiredCapability to the NavItem ` +
        `(navItems.ts) so the sidebar hides the link in core-only deployments.`,
    ).toEqual([]);
  });

  it('derivation coverage: every definition derives available=true from its sample paths', () => {
    const dead: string[] = [];
    for (const def of CAPABILITY_DEFINITIONS) {
      // Include patch so predicates that require a method (e.g. the
      // lineage field editor's PATCH contract) can match.
      const schema = {
        paths: Object.fromEntries(def.samplePaths.map((p) => [p, { get: {}, patch: {} }])),
      };
      const caps = deriveCapabilitiesFromOpenAPI(schema as never);
      if (caps[def.key]?.available !== true) {
        dead.push(def.key);
      }
    }
    expect(
      dead,
      `Capability definitions that never resolve available=true from their sample ` +
        `paths: ${JSON.stringify(dead)}. Fix the predicate/samplePaths pair — a dead ` +
        `predicate silently disables the feature in FULL mode.`,
    ).toEqual([]);
  });
});
