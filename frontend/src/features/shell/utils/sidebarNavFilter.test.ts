import { describe, expect, it } from 'vitest';
import type { NavItem } from '../components/Sidebar';
import { filterVisibleNavItems } from './sidebarNavFilter';

const sampleItems: NavItem[] = [
  { path: '/', label: 'Home' },
  { path: '/mesh', label: 'Mesh', requiredCapability: 'mesh.domains' },
  { path: '/contracts', label: 'Contracts' },
  { path: '/scheduled-ingestions', label: 'Ingest', requiredRole: ['TENANT_ADMIN'] },
];

describe('filterVisibleNavItems', () => {
  const allowAllRoles = () => true;
  const allowAllCaps = () => true;
  const denyAllCaps = () => false;

  it('removes MVP-hidden paths when MVP mode is enabled', () => {
    const out = filterVisibleNavItems(sampleItems, {
      mvpModeEnabled: true,
      hasRole: allowAllRoles,
      isCapabilityAvailable: allowAllCaps,
    });
    expect(out.map((i) => i.path)).toEqual(['/', '/contracts']);
  });

  it('keeps mesh when MVP mode is off and capability is available', () => {
    const out = filterVisibleNavItems(sampleItems, {
      mvpModeEnabled: false,
      hasRole: allowAllRoles,
      isCapabilityAvailable: allowAllCaps,
    });
    expect(out.some((i) => i.path === '/mesh')).toBe(true);
  });

  it('hides items when capability is unavailable (non-MVP)', () => {
    const out = filterVisibleNavItems(sampleItems, {
      mvpModeEnabled: false,
      hasRole: allowAllRoles,
      isCapabilityAvailable: denyAllCaps,
    });
    expect(out.some((i) => i.path === '/mesh')).toBe(false);
  });

  it('preserves the optional badge field on retained items', () => {
    const itemsWithBadge: NavItem[] = [
      { path: '/governance', label: 'Governance', badge: 7 },
      { path: '/audit', label: 'Audit', badge: 0 },
    ];
    const out = filterVisibleNavItems(itemsWithBadge, {
      mvpModeEnabled: false,
      hasRole: allowAllRoles,
      isCapabilityAvailable: allowAllCaps,
    });
    expect(out.find((i) => i.path === '/governance')?.badge).toBe(7);
    expect(out.find((i) => i.path === '/audit')?.badge).toBe(0);
  });

  // ─── Phase 240.4.A.9 — sub-menu (children) handling ────────────────

  it('recursively filters children by capability and keeps applicable parents', () => {
    const itemsWithChildren: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        children: [
          { path: '/dq/anomalies', label: 'Anomalies' },
          {
            path: '/dq/admin',
            label: 'Admin',
            requiredRole: ['TENANT_ADMIN'],
          },
          {
            path: '/dq/legacy',
            label: 'Legacy',
            requiredCapability: 'dq.legacy',
          },
        ],
      },
    ];
    const out = filterVisibleNavItems(itemsWithChildren, {
      mvpModeEnabled: false,
      hasRole: (roles) => !roles || roles.includes('DATA_PROVIDER'),
      isCapabilityAvailable: denyAllCaps,
    });
    const parent = out.find((i) => i.path === '/dq');
    expect(parent).toBeDefined();
    // Only the unconditional child survives — admin (role mismatch)
    // and legacy (capability denied) are filtered out.
    expect(parent?.children?.map((c) => c.path)).toEqual(['/dq/anomalies']);
  });

  it('drops the children field entirely when no child passes the gates (parent-only fallback)', () => {
    const itemsWithGatedChildren: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        children: [
          { path: '/dq/x', label: 'X', requiredCapability: 'unknown.cap' },
        ],
      },
    ];
    const out = filterVisibleNavItems(itemsWithGatedChildren, {
      mvpModeEnabled: false,
      hasRole: allowAllRoles,
      isCapabilityAvailable: denyAllCaps,
    });
    // Phase 240.4.A audit-fix Gap 2: when ALL children are gated out,
    // the parent stays visible WITHOUT a sub-menu so the basic
    // navigation still works (graceful degrade).
    const parent = out.find((i) => i.path === '/dq');
    expect(parent).toBeDefined();
    expect(parent?.children).toBeUndefined();
  });

  it('hides the parent itself when its own gates fail, regardless of children', () => {
    const itemsWithGatedParent: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        requiredRole: ['TENANT_ADMIN'],
        children: [{ path: '/dq/x', label: 'X' }],
      },
    ];
    const out = filterVisibleNavItems(itemsWithGatedParent, {
      mvpModeEnabled: false,
      hasRole: () => false,
      isCapabilityAvailable: allowAllCaps,
    });
    expect(out).toEqual([]);
  });
});
