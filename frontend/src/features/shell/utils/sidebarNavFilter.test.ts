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
    expect(out.map((i) => i.path)).toEqual(['/', '/contracts', '/scheduled-ingestions']);
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
});
