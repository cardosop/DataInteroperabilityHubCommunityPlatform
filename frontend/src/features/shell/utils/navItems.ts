/**
 * Shared sidebar navigation items (223.5).
 *
 * Single source of truth for the Sidebar and CommandPalette so both
 * surfaces stay in sync as routes are added / removed. Kept as a `.ts`
 * file (no JSX) to satisfy `react-refresh/only-export-components`.
 */

export interface NavItem {
  path: string;
  label: string;
  icon?: string;
  requiredRole?: string[];
  requiredCapability?: string;
  /** Optional unread-style badge shown next to the label when > 0. */
  badge?: number;
}

export const SIDEBAR_NAV_ITEMS: NavItem[] = [
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
