/**
 * flattenNavItemsForPalette — Phase 240.4.A audit-fix Gap 1 regression.
 *
 * Locks the contract that ⌘K surfaces sub-menu children, NOT just
 * top-level items.  The original closeout dropped children silently
 * via ``.map((item) => ({ label: item.label, path: item.path }))``,
 * so the new DQ dashboards (Anomalies / Trends / Scorecards / etc.)
 * never appeared in the command palette even though they were wired
 * into the Sidebar.
 */
import { describe, expect, it } from 'vitest';
import { flattenNavItemsForPalette } from './flattenNavItemsForPalette';
import type { NavItem } from './navItems';

describe('flattenNavItemsForPalette', () => {
  it('flattens a single top-level item to one palette entry', () => {
    const items: NavItem[] = [{ path: '/', label: 'Home' }];
    expect(flattenNavItemsForPalette(items)).toEqual([
      { label: 'Home', path: '/' },
    ]);
  });

  it('flattens a parent + 3 children into 4 palette entries (parent first)', () => {
    const items: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        children: [
          { path: '/dq/anomalies', label: 'Anomalies' },
          { path: '/dq/trends', label: 'Trends' },
          { path: '/dq/scorecards', label: 'Scorecards' },
        ],
      },
    ];
    const out = flattenNavItemsForPalette(items);
    expect(out).toEqual([
      { label: 'Data Quality', path: '/dq' },
      { label: 'Data Quality / Anomalies', path: '/dq/anomalies' },
      { label: 'Data Quality / Trends', path: '/dq/trends' },
      { label: 'Data Quality / Scorecards', path: '/dq/scorecards' },
    ]);
  });

  it('disambiguates child labels with the parent prefix', () => {
    // Anomalies could plausibly be a sub-item of multiple top-level
    // sections in the future — the parent prefix avoids collisions.
    const items: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        children: [{ path: '/dq/anomalies', label: 'Anomalies' }],
      },
    ];
    const out = flattenNavItemsForPalette(items);
    expect(out).toContainEqual({
      label: 'Data Quality / Anomalies',
      path: '/dq/anomalies',
    });
  });

  it('preserves declaration order: parent → its children → next parent', () => {
    const items: NavItem[] = [
      { path: '/a', label: 'A' },
      {
        path: '/b',
        label: 'B',
        children: [{ path: '/b/x', label: 'X' }],
      },
      { path: '/c', label: 'C' },
    ];
    const out = flattenNavItemsForPalette(items);
    expect(out.map((e) => e.path)).toEqual(['/a', '/b', '/b/x', '/c']);
  });

  it('handles items without children (children=undefined) without crashing', () => {
    const items: NavItem[] = [{ path: '/jobs', label: 'Jobs' }];
    const out = flattenNavItemsForPalette(items);
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({ label: 'Jobs', path: '/jobs' });
  });

  it('handles empty children array (children=[]) by emitting only the parent', () => {
    const items: NavItem[] = [
      { path: '/empty', label: 'Empty', children: [] },
    ];
    expect(flattenNavItemsForPalette(items)).toEqual([
      { label: 'Empty', path: '/empty' },
    ]);
  });

  it('regression: must surface DQ sub-items so ⌘K finds them', () => {
    // Concrete reproducer for Phase 240.4.A audit-fix Gap 1.  The
    // original closeout used ``.map((item) => ({label,path}))`` which
    // dropped the children silently.  This test pins that the new
    // implementation surfaces every DQ sub-item.
    const items: NavItem[] = [
      {
        path: '/dq',
        label: 'Data Quality',
        children: [
          { path: '/dq/anomalies', label: 'Anomalies' },
          { path: '/dq/trends', label: 'Trends' },
          { path: '/dq/scorecards', label: 'Scorecards' },
          { path: '/dq/alerting-rules', label: 'Alerting Rules' },
          { path: '/dq/rca', label: 'Root Cause' },
        ],
      },
    ];
    const paths = flattenNavItemsForPalette(items).map((e) => e.path);
    expect(paths).toContain('/dq/anomalies');
    expect(paths).toContain('/dq/trends');
    expect(paths).toContain('/dq/scorecards');
    expect(paths).toContain('/dq/alerting-rules');
    expect(paths).toContain('/dq/rca');
  });
});
