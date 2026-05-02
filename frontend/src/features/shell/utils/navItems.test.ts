/**
 * navItems.ts regression tests — Phase 240.4.A.9 + Phase 240.4.B.4.
 *
 * Phase 240.4.A audit-fix Gap 2: the original 240.4.A closeout gated
 * sub-items on ``requiredCapability: 'data_quality_advanced_enabled'``
 * — a capability key that wasn't registered in the backend
 * ``/capabilities`` response, so ``isCapabilityAvailable`` returned
 * ``false`` for it and hid the whole sub-menu permanently.
 *
 * Phase 240.4.B.4 introduces REAL capability keys
 * (``data_quality`` / ``data_quality_advanced``) that the backend
 * ``GET /api/v1/capabilities/`` endpoint resolves from
 * ``Tenant.data_quality_enabled`` / ``Tenant.data_quality_advanced_enabled``.
 * The sidebar gate now keys on those — so when a tenant has the
 * advanced flag off, the sub-menu hides correctly; when both flags
 * are on, it surfaces.
 */
import { describe, expect, it } from 'vitest';
import { SIDEBAR_NAV_ITEMS } from './navItems';
import { filterVisibleNavItems } from './sidebarNavFilter';

describe('SIDEBAR_NAV_ITEMS — DQ sub-menu (Phase 240.4.A.9 + Phase 240.4.B.4)', () => {
  function findDqEntry() {
    return SIDEBAR_NAV_ITEMS.find((i) => i.path === '/dq');
  }

  it('declares /dq with five children', () => {
    const dq = findDqEntry();
    expect(dq).toBeDefined();
    expect(dq?.children).toBeDefined();
    expect(dq?.children?.map((c) => c.path)).toEqual([
      '/dq/anomalies',
      '/dq/trends',
      '/dq/scorecards',
      '/dq/alerting-rules',
      '/dq/rca',
    ]);
  });

  it('parent /dq is gated on the ``data_quality`` capability (Phase 240.4.B.4)', () => {
    expect(findDqEntry()?.requiredCapability).toBe('data_quality');
  });

  it('every sub-item is gated on the ``data_quality_advanced`` capability', () => {
    const dq = findDqEntry();
    for (const child of dq?.children ?? []) {
      expect(child.requiredCapability).toBe('data_quality_advanced');
    }
  });

  it('does NOT gate on the non-existent ``data_quality_advanced_enabled`` key (Gap 2 regression)', () => {
    // Phase 240.4.A audit-fix Gap 2 regression: ``data_quality_advanced_enabled``
    // (with the trailing _enabled) was NEVER registered in the backend
    // ``/capabilities`` map.  The correct key is ``data_quality_advanced``
    // (without _enabled).  This test pins the spelling.
    const dq = findDqEntry();
    expect(dq?.requiredCapability).not.toBe('data_quality_enabled');
    for (const child of dq?.children ?? []) {
      expect(child.requiredCapability).not.toBe('data_quality_advanced_enabled');
    }
  });

  it('hides the entire DQ entry when ``data_quality`` capability is False', () => {
    const out = filterVisibleNavItems(SIDEBAR_NAV_ITEMS, {
      mvpModeEnabled: false,
      hasRole: () => true,
      // Tenant has data_quality=False — kill-switch in effect.
      isCapabilityAvailable: () => false,
    });
    expect(out.find((i) => i.path === '/dq')).toBeUndefined();
  });

  it('shows /dq parent only (no sub-menu) when only the BASE flag is on', () => {
    const out = filterVisibleNavItems(SIDEBAR_NAV_ITEMS, {
      mvpModeEnabled: false,
      hasRole: () => true,
      isCapabilityAvailable: (key) => key === 'data_quality',
    });
    const dq = out.find((i) => i.path === '/dq');
    expect(dq).toBeDefined();
    // ``data_quality_advanced`` is False → all 5 children gated out →
    // parent surfaces with no children (graceful degrade per Phase
    // 240.4.A.9 sub-menu fallback in sidebarNavFilter.ts).
    expect(dq?.children).toBeUndefined();
  });

  it('shows the full DQ sub-menu when BOTH capabilities are on', () => {
    const out = filterVisibleNavItems(SIDEBAR_NAV_ITEMS, {
      mvpModeEnabled: false,
      hasRole: (roles) =>
        !roles || roles.includes('TENANT_ADMIN') || roles.includes('PLATFORM_ADMIN'),
      isCapabilityAvailable: (key) =>
        key === 'data_quality' || key === 'data_quality_advanced',
    });
    const dq = out.find((i) => i.path === '/dq');
    expect(dq).toBeDefined();
    expect(dq?.children?.length).toBe(5);
    expect(dq?.children?.map((c) => c.path).sort()).toEqual([
      '/dq/alerting-rules',
      '/dq/anomalies',
      '/dq/rca',
      '/dq/scorecards',
      '/dq/trends',
    ]);
  });

  it('hides Alerting Rules when both caps are on but the user is not a tenant admin', () => {
    const out = filterVisibleNavItems(SIDEBAR_NAV_ITEMS, {
      mvpModeEnabled: false,
      hasRole: (roles) => !roles || roles.includes('DATA_PROVIDER'),
      isCapabilityAvailable: (key) =>
        key === 'data_quality' || key === 'data_quality_advanced',
    });
    const dq = out.find((i) => i.path === '/dq');
    expect(dq?.children?.map((c) => c.path)).not.toContain('/dq/alerting-rules');
    // The four read-only sub-items remain visible.
    expect(dq?.children?.length).toBe(4);
  });
});
