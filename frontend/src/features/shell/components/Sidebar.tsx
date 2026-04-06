/**
 * Sidebar Navigation Component
 * Role-aware sidebar navigation based on user roles
 */

import { NavLink } from 'react-router-dom';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { useAuthStore } from '../../auth/store/authStore';
import { isMvpModeEnabledFromEnv } from '../utils/mvpNav';
import { filterVisibleNavItems } from '../utils/sidebarNavFilter';
import './Sidebar.css';

export interface NavItem {
  path: string;
  label: string;
  icon?: string;
  requiredRole?: string[];
  requiredCapability?: string;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Home', icon: '🏠' },
  {
    path: '/assets',
    label: 'Assets',
    icon: '📦',
    requiredRole: ['DATA_PROVIDER', 'DATA_CONSUMER'],
  },
  { path: '/datasets', label: 'Datasets', icon: '📊' },
  { path: '/files', label: 'Files', icon: '📁' },
  { path: '/contracts', label: 'Contracts', icon: '📄' },
  { path: '/marketplace', label: 'Marketplace', icon: '🛒' },
  {
    path: '/integrations/connections',
    label: 'Integrations',
    icon: '🔌',
    requiredCapability: 'integrations.marketplace',
  },
  { path: '/dq', label: 'Data Quality', icon: '✅' },
  { path: '/compliance', label: 'Compliance', icon: '🛡️' },
  { path: '/mesh', label: 'Data Mesh', icon: '🌐', requiredCapability: 'mesh.domains' },
  {
    path: '/virtualization',
    label: 'Virtualization',
    icon: '🔮',
    requiredCapability: 'virtualization.datasets',
  },
  { path: '/search', label: 'Search', icon: '🔍' },
  {
    path: '/semantic',
    label: 'Semantic',
    icon: '🔗',
    requiredCapability: 'semantic.sparql',
  },
  {
    path: '/ai/search',
    label: 'AI Search',
    icon: '🤖',
    requiredCapability: 'ai.natural-language-search',
  },
  {
    path: '/ai/schema-matching',
    label: 'Schema Matching',
    icon: '🔀',
    requiredCapability: 'ai.schema-matching',
  },
  { path: '/communities', label: 'Communities', icon: '👥', requiredCapability: 'social.communities' },
  { path: '/developer', label: 'Developer', icon: '🛠️', requiredCapability: 'developer.plugins' },
  { path: '/baas', label: 'BaaS', icon: '🔑', requiredCapability: 'baas.api-keys' },
  { path: '/ml', label: 'ML', icon: '🧠', requiredCapability: 'ml.models' },
  { path: '/observability', label: 'Observability', icon: '📈' },
  {
    path: '/transformation',
    label: 'Transformation',
    icon: '🔄',
    requiredCapability: 'transformation',
  },
  { path: '/jobs', label: 'Jobs', icon: '⚙️' },
  { path: '/webhooks', label: 'Webhooks', icon: '🔗' },
  {
    path: '/governance',
    label: 'Governance',
    icon: '📋',
    requiredRole: ['TENANT_ADMIN', 'PLATFORM_ADMIN'],
  },
  {
    path: '/audit',
    label: 'Audit',
    icon: '🔍',
    requiredRole: ['AUDITOR', 'TENANT_ADMIN', 'PLATFORM_ADMIN'],
  },
  {
    path: '/scheduled-ingestions',
    label: 'Scheduled Ingestion',
    icon: '⏰',
    requiredRole: ['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN'],
  },
  { path: '/admin', label: 'Admin', icon: '⚙️', requiredRole: ['TENANT_ADMIN', 'PLATFORM_ADMIN'] },
];

export function Sidebar() {
  const { user } = useAuthStore();
  const { isCapabilityAvailable } = useCapabilities();

  const hasRole = (requiredRoles?: string[]): boolean => {
    if (!requiredRoles || requiredRoles.length === 0) return true;
    if (!user) return false;
    return requiredRoles.some((role) => user.roles.includes(role));
  };

  const filteredNavItems = filterVisibleNavItems(navItems, {
    mvpModeEnabled: isMvpModeEnabledFromEnv(),
    hasRole,
    isCapabilityAvailable,
  });

  // Group nav items into sections
  const corePaths = new Set(['/', '/assets', '/datasets', '/contracts']);
  const qualityPaths = new Set(['/dq', '/compliance']);
  const discoverPaths = new Set(['/search', '/marketplace']);
  const adminPaths = new Set(['/jobs', '/webhooks', '/observability', '/governance', '/audit', '/admin', '/files', '/semantic', '/scheduled-ingestions']);

  const coreItems = filteredNavItems.filter((i) => corePaths.has(i.path));
  const qualityItems = filteredNavItems.filter((i) => qualityPaths.has(i.path));
  const discoverItems = filteredNavItems.filter((i) => discoverPaths.has(i.path));
  const adminItems = filteredNavItems.filter((i) => adminPaths.has(i.path));
  const otherItems = filteredNavItems.filter(
    (i) => !corePaths.has(i.path) && !qualityPaths.has(i.path) && !discoverPaths.has(i.path) && !adminPaths.has(i.path),
  );

  const renderItems = (items: NavItem[]) =>
    items.map((item) => (
      <li key={item.path}>
        <NavLink
          to={item.path}
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          end={item.path === '/'}
        >
          {item.icon && <span className="nav-icon">{item.icon}</span>}
          <span className="nav-label">{item.label}</span>
        </NavLink>
      </li>
    ));

  return (
    <aside className="app-sidebar" role="navigation" aria-label="Main navigation">
      <nav className="sidebar-nav">
        {coreItems.length > 0 && (
          <ul className="nav-list">{renderItems(coreItems)}</ul>
        )}
        {qualityItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">Quality & Compliance</summary>
            <ul className="nav-list">{renderItems(qualityItems)}</ul>
          </details>
        )}
        {discoverItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">Discover</summary>
            <ul className="nav-list">{renderItems(discoverItems)}</ul>
          </details>
        )}
        {otherItems.length > 0 && (
          <details className="nav-group" open>
            <summary className="nav-group__label">More</summary>
            <ul className="nav-list">{renderItems(otherItems)}</ul>
          </details>
        )}
        {adminItems.length > 0 && (
          <details className="nav-group">
            <summary className="nav-group__label">Admin</summary>
            <ul className="nav-list">{renderItems(adminItems)}</ul>
          </details>
        )}
      </nav>
    </aside>
  );
}
