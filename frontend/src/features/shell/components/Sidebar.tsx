/**
 * Sidebar Navigation Component
 * Role-aware sidebar navigation based on user roles
 */

import { NavLink } from 'react-router-dom';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { useAuthStore } from '../../auth/store/authStore';
import './Sidebar.css';

interface NavItem {
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
  { path: '/integrations/connections', label: 'Integrations', icon: '🔌' },
  { path: '/odps', label: 'ODPS', icon: '🔗' },
  { path: '/dq', label: 'Data Quality', icon: '✅' },
  { path: '/compliance', label: 'Compliance', icon: '🛡️' },
  { path: '/mesh', label: 'Data Mesh', icon: '🌐' },
  { path: '/virtualization', label: 'Virtualization', icon: '🔮' },
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

  const filteredNavItems = navItems.filter((item) => {
    // Check role requirement
    if (!hasRole(item.requiredRole)) {
      return false;
    }

    // Check capability requirement
    if (item.requiredCapability) {
      return isCapabilityAvailable(item.requiredCapability);
    }

    return true;
  });

  return (
    <aside className="app-sidebar" role="navigation" aria-label="Main navigation">
      <nav className="sidebar-nav">
        <ul className="nav-list">
          {filteredNavItems.map((item) => (
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
          ))}
        </ul>
      </nav>
    </aside>
  );
}
