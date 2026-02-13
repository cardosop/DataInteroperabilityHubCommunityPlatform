/**
 * Application Routes
 * Defines all routes with protection and capability gating
 */
/* eslint-disable react-refresh/only-export-components */

import { lazy, Suspense } from 'react';
import { createBrowserRouter, Outlet } from 'react-router-dom';
// Critical routes - eagerly loaded (login, public pages)
import { AcceptInvitationPage } from '../../features/auth/components/AcceptInvitationPage';
import { LoginPage } from '../../features/auth/components/LoginPage';
import { PasswordResetConfirmPage } from '../../features/auth/components/PasswordResetConfirmPage';
import { PasswordResetPage } from '../../features/auth/components/PasswordResetPage';
import { PublicResourcesPage } from '../../features/auth/components/PublicResourcesPage';
import { RegisterPage } from '../../features/auth/components/RegisterPage';
import { RegistrationRoute } from '../../features/auth/components/RegistrationRoute';
import { AppShell } from '../../features/shell/components/AppShell';
import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
import { LoadingSpinner } from '../../shared/components/LoadingSpinner';
import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { UnavailablePage } from '../../shared/components/UnavailablePage';

// Lazy load non-critical routes for code splitting
const AISearchPage = lazy(() =>
  import('../../features/ai/components/AISearchPage').then((m) => ({ default: m.AISearchPage }))
);
const SchemaMatchingPage = lazy(() =>
  import('../../features/ai/components/SchemaMatchingPage').then((m) => ({
    default: m.SchemaMatchingPage,
  }))
);
const AssetCreatePage = lazy(() =>
  import('../../features/assets/components/AssetCreatePage').then((m) => ({
    default: m.AssetCreatePage,
  }))
);
const AssetDetailPage = lazy(() =>
  import('../../features/assets/components/AssetDetailPage').then((m) => ({
    default: m.AssetDetailPage,
  }))
);
const AssetListPage = lazy(() =>
  import('../../features/assets/components/AssetListPage').then((m) => ({
    default: m.AssetListPage,
  }))
);
const AuditEventDetailPage = lazy(() =>
  import('../../features/audit/components/AuditEventDetailPage').then((m) => ({
    default: m.AuditEventDetailPage,
  }))
);
const AuditEventListPage = lazy(() =>
  import('../../features/audit/components/AuditEventListPage').then((m) => ({
    default: m.AuditEventListPage,
  }))
);
const AuthAPIKeyListPage = lazy(() =>
  import('../../features/auth/components/AuthAPIKeyListPage').then((m) => ({
    default: m.AuthAPIKeyListPage,
  }))
);
const SessionListPage = lazy(() =>
  import('../../features/auth/components/SessionListPage').then((m) => ({
    default: m.SessionListPage,
  }))
);
const BaaSPage = lazy(() =>
  import('../../features/baas/components/BaaSPage').then((m) => ({ default: m.BaaSPage }))
);
const ComplianceRunDetailPage = lazy(() =>
  import('../../features/compliance/components/ComplianceRunDetailPage').then((m) => ({
    default: m.ComplianceRunDetailPage,
  }))
);
const ComplianceRunListPage = lazy(() =>
  import('../../features/compliance/components/ComplianceRunListPage').then((m) => ({
    default: m.ComplianceRunListPage,
  }))
);
const ContractDetailPage = lazy(() =>
  import('../../features/contracts/components/ContractDetailPage').then((m) => ({
    default: m.ContractDetailPage,
  }))
);
const ContractEditorPage = lazy(() =>
  import('../../features/contracts/components/ContractEditorPage').then((m) => ({
    default: m.ContractEditorPage,
  }))
);
const ContractListPage = lazy(() =>
  import('../../features/contracts/components/ContractListPage').then((m) => ({
    default: m.ContractListPage,
  }))
);
const DatasetCreatePage = lazy(() =>
  import('../../features/datasets/components/DatasetCreatePage').then((m) => ({
    default: m.DatasetCreatePage,
  }))
);
const DatasetDetailPage = lazy(() =>
  import('../../features/datasets/components/DatasetDetailPage').then((m) => ({
    default: m.DatasetDetailPage,
  }))
);
const DatasetListPage = lazy(() =>
  import('../../features/datasets/components/DatasetListPage').then((m) => ({
    default: m.DatasetListPage,
  }))
);
const DatasetVersionsPage = lazy(() =>
  import('../../features/datasets/components/DatasetVersionsPage').then((m) => ({
    default: m.DatasetVersionsPage,
  }))
);
const DeveloperPortalPage = lazy(() =>
  import('../../features/developer/components/DeveloperPortalPage').then((m) => ({
    default: m.DeveloperPortalPage,
  }))
);
const DQRunDetailPage = lazy(() =>
  import('../../features/dq/components/DQRunDetailPage').then((m) => ({
    default: m.DQRunDetailPage,
  }))
);
const DQRunListPage = lazy(() =>
  import('../../features/dq/components/DQRunListPage').then((m) => ({ default: m.DQRunListPage }))
);
const FileListPage = lazy(() =>
  import('../../features/files/components/FileListPage').then((m) => ({ default: m.FileListPage }))
);
const AccessRequestCreatePage = lazy(() =>
  import('../../features/governance/components/AccessRequestCreatePage').then((m) => ({
    default: m.AccessRequestCreatePage,
  }))
);
const AccessRequestDetailPage = lazy(() =>
  import('../../features/governance/components/AccessRequestDetailPage').then((m) => ({
    default: m.AccessRequestDetailPage,
  }))
);
const AccessRequestListPage = lazy(() =>
  import('../../features/governance/components/AccessRequestListPage').then((m) => ({
    default: m.AccessRequestListPage,
  }))
);
const RetentionPolicyListPage = lazy(() =>
  import('../../features/governance/components/RetentionPolicyListPage').then((m) => ({
    default: m.RetentionPolicyListPage,
  }))
);
const RetentionPolicyDetailPage = lazy(() =>
  import('../../features/governance/components/RetentionPolicyDetailPage').then((m) => ({
    default: m.RetentionPolicyDetailPage,
  }))
);
const RetentionPolicyCreatePage = lazy(() =>
  import('../../features/governance/components/RetentionPolicyCreatePage').then((m) => ({
    default: m.RetentionPolicyCreatePage,
  }))
);
const RetentionPolicyEditPage = lazy(() =>
  import('../../features/governance/components/RetentionPolicyEditPage').then((m) => ({
    default: m.RetentionPolicyEditPage,
  }))
);
const JobDetailPage = lazy(() =>
  import('../../features/jobs/components/JobDetailPage').then((m) => ({ default: m.JobDetailPage }))
);
const JobListPage = lazy(() =>
  import('../../features/jobs/components/JobListPage').then((m) => ({ default: m.JobListPage }))
);
const MeshDomainCreatePage = lazy(() =>
  import('../../features/mesh/components/MeshDomainCreatePage').then((m) => ({
    default: m.MeshDomainCreatePage,
  }))
);
const MeshDomainDetailPage = lazy(() =>
  import('../../features/mesh/components/MeshDomainDetailPage').then((m) => ({
    default: m.MeshDomainDetailPage,
  }))
);
const MeshDomainListPage = lazy(() =>
  import('../../features/mesh/components/MeshDomainListPage').then((m) => ({
    default: m.MeshDomainListPage,
  }))
);
const TopologyVisualization = lazy(() =>
  import('../../features/mesh/components/TopologyVisualization').then((m) => ({
    default: m.TopologyVisualization,
  }))
);
const MLPage = lazy(() =>
  import('../../features/ml/components/MLPage').then((m) => ({ default: m.MLPage }))
);
const ObservabilityPage = lazy(() =>
  import('../../features/observability/components/ObservabilityPage').then((m) => ({
    default: m.ObservabilityPage,
  }))
);
const ODPSDetailPage = lazy(() =>
  import('../../features/odps/components/ODPSDetailPage').then((m) => ({
    default: m.ODPSDetailPage,
  }))
);
const ODPSLinkPage = lazy(() =>
  import('../../features/odps/components/ODPSLinkPage').then((m) => ({ default: m.ODPSLinkPage }))
);
const ODPSListPage = lazy(() =>
  import('../../features/odps/components/ODPSListPage').then((m) => ({ default: m.ODPSListPage }))
);
const ODPSUploadPage = lazy(() =>
  import('../../features/odps/components/ODPSUploadPage').then((m) => ({
    default: m.ODPSUploadPage,
  }))
);
const ScheduledIngestionCreatePage = lazy(() =>
  import('../../features/scheduledIngestion/components/ScheduledIngestionCreatePage').then((m) => ({
    default: m.ScheduledIngestionCreatePage,
  }))
);
const ScheduledIngestionDetailPage = lazy(() =>
  import('../../features/scheduledIngestion/components/ScheduledIngestionDetailPage').then((m) => ({
    default: m.ScheduledIngestionDetailPage,
  }))
);
const ScheduledIngestionEditPage = lazy(() =>
  import('../../features/scheduledIngestion/components/ScheduledIngestionEditPage').then((m) => ({
    default: m.ScheduledIngestionEditPage,
  }))
);
const ScheduledIngestionListPage = lazy(() =>
  import('../../features/scheduledIngestion/components/ScheduledIngestionListPage').then((m) => ({
    default: m.ScheduledIngestionListPage,
  }))
);
const ScheduledExportCreatePage = lazy(() =>
  import('../../features/scheduledExport/components/ScheduledExportCreatePage').then((m) => ({
    default: m.ScheduledExportCreatePage,
  }))
);
const ScheduledExportDetailPage = lazy(() =>
  import('../../features/scheduledExport/components/ScheduledExportDetailPage').then((m) => ({
    default: m.ScheduledExportDetailPage,
  }))
);
const ScheduledExportEditPage = lazy(() =>
  import('../../features/scheduledExport/components/ScheduledExportEditPage').then((m) => ({
    default: m.ScheduledExportEditPage,
  }))
);
const ScheduledExportListPage = lazy(() =>
  import('../../features/scheduledExport/components/ScheduledExportListPage').then((m) => ({
    default: m.ScheduledExportListPage,
  }))
);
const SearchPage = lazy(() =>
  import('../../features/search/components/SearchPage').then((m) => ({ default: m.SearchPage }))
);
const SemanticPage = lazy(() =>
  import('../../features/semantic/components/SemanticPage').then((m) => ({
    default: m.SemanticPage,
  }))
);
const SocialPage = lazy(() =>
  import('../../features/social/components/SocialPage').then((m) => ({ default: m.SocialPage }))
);
const VirtualDatasetCreatePage = lazy(() =>
  import('../../features/virtualization/components/VirtualDatasetCreatePage').then((m) => ({
    default: m.VirtualDatasetCreatePage,
  }))
);
const VirtualDatasetDetailPage = lazy(() =>
  import('../../features/virtualization/components/VirtualDatasetDetailPage').then((m) => ({
    default: m.VirtualDatasetDetailPage,
  }))
);
const VirtualDatasetEditPage = lazy(() =>
  import('../../features/virtualization/components/VirtualDatasetEditPage').then((m) => ({
    default: m.VirtualDatasetEditPage,
  }))
);
const VirtualDatasetListPage = lazy(() =>
  import('../../features/virtualization/components/VirtualDatasetListPage').then((m) => ({
    default: m.VirtualDatasetListPage,
  }))
);
const WebhookCreatePage = lazy(() =>
  import('../../features/webhooks/components/WebhookCreatePage').then((m) => ({
    default: m.WebhookCreatePage,
  }))
);
const WebhookDetailPage = lazy(() =>
  import('../../features/webhooks/components/WebhookDetailPage').then((m) => ({
    default: m.WebhookDetailPage,
  }))
);
const WebhookEditPage = lazy(() =>
  import('../../features/webhooks/components/WebhookEditPage').then((m) => ({
    default: m.WebhookEditPage,
  }))
);
const WebhookListPage = lazy(() =>
  import('../../features/webhooks/components/WebhookListPage').then((m) => ({
    default: m.WebhookListPage,
  }))
);

const MeshPage = () => <Outlet />;
const VirtualizationPage = () => <Outlet />;
const GovernanceLayout = () => <Outlet />;

// Lazy load marketplace components to isolate any loading issues
const ListingListPage = lazy(() =>
  import('../../features/marketplace/components/ListingListPage').then((m) => ({
    default: m.ListingListPage,
  }))
);
const ListingDetailPage = lazy(() =>
  import('../../features/marketplace/components/ListingDetailPage').then((m) => ({
    default: m.ListingDetailPage,
  }))
);
const ListingPublishPage = lazy(() =>
  import('../../features/marketplace/components/ListingPublishPage').then((m) => ({
    default: m.ListingPublishPage,
  }))
);
const OrderListPage = lazy(() =>
  import('../../features/marketplace/components/OrderListPage').then((m) => ({
    default: m.OrderListPage,
  }))
);
const OrderDetailPage = lazy(() =>
  import('../../features/marketplace/components/OrderDetailPage').then((m) => ({
    default: m.OrderDetailPage,
  }))
);
const EntitlementListPage = lazy(() =>
  import('../../features/marketplace/components/EntitlementListPage').then((m) => ({
    default: m.EntitlementListPage,
  }))
);
const EntitlementDetailPage = lazy(() =>
  import('../../features/marketplace/components/EntitlementDetailPage').then((m) => ({
    default: m.EntitlementDetailPage,
  }))
);
const MarketplaceConnectionListPage = lazy(() =>
  import('../../features/integrations/components/MarketplaceConnectionListPage').then((m) => ({
    default: m.MarketplaceConnectionListPage,
  }))
);
const MarketplaceConnectionCreatePage = lazy(() =>
  import('../../features/integrations/components/MarketplaceConnectionCreatePage').then((m) => ({
    default: m.MarketplaceConnectionCreatePage,
  }))
);
const MarketplaceConnectionDetailPage = lazy(() =>
  import('../../features/integrations/components/MarketplaceConnectionDetailPage').then((m) => ({
    default: m.MarketplaceConnectionDetailPage,
  }))
);
const MarketplaceConnectionEditPage = lazy(() =>
  import('../../features/integrations/components/MarketplaceConnectionEditPage').then((m) => ({
    default: m.MarketplaceConnectionEditPage,
  }))
);
const MarketplaceSyncJobListPage = lazy(() =>
  import('../../features/integrations/components/MarketplaceSyncJobListPage').then((m) => ({
    default: m.MarketplaceSyncJobListPage,
  }))
);
const MarketplaceMappingListPage = lazy(() =>
  import('../../features/integrations/components/MarketplaceMappingListPage').then((m) => ({
    default: m.MarketplaceMappingListPage,
  }))
);

// Lazy load heavy pages for code splitting
const AdminPage = lazy(() =>
  import('../../features/admin/components/AdminPage').then((m) => ({
    default: m.AdminPage,
  }))
);
const HomePage = lazy(() =>
  import('../pages/HomePage').then((m) => ({
    default: m.HomePage,
  }))
);
const NotFoundPage = lazy(() =>
  Promise.resolve({
    default: () => <div>404 - Page Not Found</div>,
  })
);
const ForbiddenPage = lazy(() =>
  Promise.resolve({
    default: () => <div>403 - Forbidden</div>,
  })
);

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/public',
    element: <PublicResourcesPage />,
  },
  {
    path: '/register',
    element: (
      <RegistrationRoute>
        <RegisterPage />
      </RegistrationRoute>
    ),
  },
  {
    path: '/password-reset',
    element: (
      <CapabilityRoute capability="auth.password-reset">
        <PasswordResetPage />
      </CapabilityRoute>
    ),
  },
  {
    path: '/password-reset/confirm',
    element: (
      <CapabilityRoute capability="auth.password-reset-confirm">
        <PasswordResetConfirmPage />
      </CapabilityRoute>
    ),
  },
  // Compatibility with backend-generated email links
  {
    path: '/auth/password-reset/confirm',
    element: (
      <CapabilityRoute capability="auth.password-reset-confirm">
        <PasswordResetConfirmPage />
      </CapabilityRoute>
    ),
  },
  {
    path: '/accept-invitation',
    element: <AcceptInvitationPage />,
  },
  {
    path: '/auth/accept-invitation',
    element: <AcceptInvitationPage />,
  },
  {
    path: '/unavailable',
    element: <UnavailablePage />,
  },
  {
    path: '/403',
    element: (
      <Suspense fallback={<LoadingSpinner message="Loading..." />}>
        <ForbiddenPage />
      </Suspense>
    ),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<LoadingSpinner message="Loading dashboard..." />}>
            <HomePage />
          </Suspense>
        ),
      },
      {
        path: 'assets',
        children: [
          {
            index: true,
            element: <AssetListPage />,
          },
          {
            path: 'create',
            element: <AssetCreatePage />,
          },
          {
            path: ':id',
            element: <AssetDetailPage />,
          },
        ],
      },
      {
        path: 'datasets',
        children: [
          {
            index: true,
            element: <DatasetListPage />,
          },
          {
            path: 'create',
            element: <DatasetCreatePage />,
          },
          {
            path: ':id',
            element: <DatasetDetailPage />,
          },
          {
            path: ':id/versions',
            element: <DatasetVersionsPage />,
          },
        ],
      },
      {
        path: 'files',
        children: [
          {
            index: true,
            element: <FileListPage />,
          },
        ],
      },
      {
        path: 'contracts',
        children: [
          {
            index: true,
            element: <ContractListPage />,
          },
          {
            path: ':id',
            element: <ContractDetailPage />,
          },
          {
            path: ':id/edit',
            element: <ContractEditorPage />,
          },
          {
            path: ':id/link-odps',
            element: <ODPSLinkPage />,
          },
        ],
      },
      {
        path: 'marketplace',
        children: [
          {
            index: true,
            element: (
              <Suspense fallback={<LoadingSpinner message="Loading marketplace..." />}>
                <ListingListPage />
              </Suspense>
            ),
          },
          {
            path: 'listings/:id',
            element: (
              <Suspense fallback={<LoadingSpinner message="Loading listing..." />}>
                <ListingDetailPage />
              </Suspense>
            ),
          },
          {
            path: 'publish',
            element: (
              <Suspense fallback={<LoadingSpinner message="Loading publish page..." />}>
                <ListingPublishPage />
              </Suspense>
            ),
          },
          {
            path: 'orders',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading orders..." />}>
                    <OrderListPage />
                  </Suspense>
                ),
              },
              {
                path: ':id',
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading order..." />}>
                    <OrderDetailPage />
                  </Suspense>
                ),
              },
            ],
          },
          {
            path: 'entitlements',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading entitlements..." />}>
                    <EntitlementListPage />
                  </Suspense>
                ),
              },
              {
                path: ':id',
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading entitlement..." />}>
                    <EntitlementDetailPage />
                  </Suspense>
                ),
              },
            ],
          },
        ],
      },
      {
        path: 'integrations',
        children: [
          {
            path: 'connections',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading connections..." />}>
                    <MarketplaceConnectionListPage />
                  </Suspense>
                ),
              },
              {
                path: 'create',
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading..." />}>
                    <MarketplaceConnectionCreatePage />
                  </Suspense>
                ),
              },
              {
                path: ':id/edit',
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading..." />}>
                    <MarketplaceConnectionEditPage />
                  </Suspense>
                ),
              },
              {
                path: ':id',
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading connection..." />}>
                    <MarketplaceConnectionDetailPage />
                  </Suspense>
                ),
              },
            ],
          },
          {
            path: 'sync-jobs',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading sync jobs..." />}>
                    <MarketplaceSyncJobListPage />
                  </Suspense>
                ),
              },
            ],
          },
          {
            path: 'mappings',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner message="Loading mappings..." />}>
                    <MarketplaceMappingListPage />
                  </Suspense>
                ),
              },
            ],
          },
        ],
      },
      {
        path: 'odps',
        children: [
          {
            index: true,
            element: <ODPSListPage />,
          },
          {
            path: 'upload',
            element: <ODPSUploadPage />,
          },
          {
            path: ':id',
            element: <ODPSDetailPage />,
          },
        ],
      },
      {
        path: 'dq',
        children: [
          {
            index: true,
            element: <DQRunListPage />,
          },
          {
            path: 'runs/:id',
            element: <DQRunDetailPage />,
          },
        ],
      },
      {
        path: 'compliance',
        children: [
          {
            index: true,
            element: <ComplianceRunListPage />,
          },
          {
            path: 'runs/:id',
            element: <ComplianceRunDetailPage />,
          },
        ],
      },
      {
        path: 'mesh',
        element: <MeshPage />,
        children: [
          { index: true, element: <MeshDomainListPage /> },
          { path: 'topology', element: <TopologyVisualization /> },
          { path: 'create', element: <MeshDomainCreatePage /> },
          { path: ':id', element: <MeshDomainDetailPage /> },
        ],
      },
      {
        path: 'virtualization',
        element: <VirtualizationPage />,
        children: [
          { index: true, element: <VirtualDatasetListPage /> },
          { path: 'create', element: <VirtualDatasetCreatePage /> },
          { path: ':id/edit', element: <VirtualDatasetEditPage /> },
          { path: ':id', element: <VirtualDatasetDetailPage /> },
        ],
      },
      {
        path: 'search',
        element: <SearchPage />,
      },
      {
        path: 'semantic',
        element: (
          <CapabilityRoute capability="semantic.sparql">
            <SemanticPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'ai/search',
        element: (
          <CapabilityRoute capability="ai.natural-language-search">
            <AISearchPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'ai/schema-matching',
        element: (
          <CapabilityRoute capability="ai.schema-matching">
            <SchemaMatchingPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'social',
        element: (
          <CapabilityRoute capability="social.ratings">
            <SocialPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'developer',
        element: (
          <CapabilityRoute capability="developer.plugins">
            <DeveloperPortalPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'baas',
        element: (
          <CapabilityRoute capability="baas.api-keys">
            <BaaSPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'ml',
        element: (
          <CapabilityRoute capability="ml.models">
            <MLPage />
          </CapabilityRoute>
        ),
      },
      {
        path: 'observability',
        element: <ObservabilityPage />,
      },
      {
        path: 'jobs',
        children: [
          {
            index: true,
            element: <JobListPage />,
          },
          {
            path: ':id',
            element: <JobDetailPage />,
          },
        ],
      },
      {
        path: 'webhooks',
        children: [
          {
            index: true,
            element: <WebhookListPage />,
          },
          {
            path: 'create',
            element: <WebhookCreatePage />,
          },
          {
            path: ':id',
            element: <WebhookDetailPage />,
          },
          {
            path: ':id/edit',
            element: <WebhookEditPage />,
          },
        ],
      },
      {
        path: 'governance',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <GovernanceLayout />
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <AccessRequestListPage /> },
          { path: 'access-requests/create', element: <AccessRequestCreatePage /> },
          { path: 'access-requests/:id', element: <AccessRequestDetailPage /> },
          { path: 'retention', element: <RetentionPolicyListPage /> },
          { path: 'retention/new', element: <RetentionPolicyCreatePage /> },
          { path: 'retention/:id', element: <RetentionPolicyDetailPage /> },
          { path: 'retention/:id/edit', element: <RetentionPolicyEditPage /> },
        ],
      },
      {
        path: 'audit',
        element: (
          <ProtectedRoute requiredRole={['AUDITOR', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <AuditEventListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'audit/:id',
        element: (
          <ProtectedRoute requiredRole={['AUDITOR', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <AuditEventDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledIngestionListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/create',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledIngestionCreatePage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/:id',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledIngestionDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/:id/edit',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledIngestionEditPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-exports',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledExportListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-exports/create',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledExportCreatePage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-exports/:id',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledExportDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'scheduled-exports/:id/edit',
        element: (
          <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <ScheduledExportEditPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'admin',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <Suspense fallback={<LoadingSpinner message="Loading admin..." />}>
              <AdminPage />
            </Suspense>
          </ProtectedRoute>
        ),
      },
      {
        path: 'settings',
        children: [
          { path: 'sessions', element: <SessionListPage /> },
          { path: 'api-keys', element: <AuthAPIKeyListPage /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: (
      <Suspense fallback={<LoadingSpinner message="Loading..." />}>
        <NotFoundPage />
      </Suspense>
    ),
  },
]);
