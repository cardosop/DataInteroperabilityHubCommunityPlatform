/**
 * Application Routes
 * Defines all routes with protection and capability gating
 */
/* eslint-disable react-refresh/only-export-components */

import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
// Critical routes - eagerly loaded (login, public pages)
import { AcceptInvitationPage } from '../../features/auth/components/AcceptInvitationPage';
import { LoginPage } from '../../features/auth/components/LoginPage';
import { VerifyEmailPage } from '../../features/auth/components/VerifyEmailPage';
// OrgOnboardingPage removed — org creation is now a Platform Admin function in /admin
import { PasswordResetConfirmPage } from '../../features/auth/components/PasswordResetConfirmPage';
import { PasswordResetPage } from '../../features/auth/components/PasswordResetPage';
import { PublicResourcesPage } from '../../features/auth/components/PublicResourcesPage';
import { RegisterPage } from '../../features/auth/components/RegisterPage';
import { RegistrationRoute } from '../../features/auth/components/RegistrationRoute';
import { RootRoute } from './RootRoute';
import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { LoadingSpinner } from '../../shared/components/LoadingSpinner';
import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { ComingSoonPage } from '../../shared/components/ComingSoonPage';
import { UnavailablePage } from '../../shared/components/UnavailablePage';

/** Wrap a lazy-loaded page in both Suspense and ErrorBoundary */
function EB({ fallbackMsg, children }: { fallbackMsg: string; children: ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner message={fallbackMsg} />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

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
const SubscriptionPage = lazy(() =>
  import('../../features/billing/components/SubscriptionPage').then((m) => ({
    default: m.SubscriptionPage,
  }))
);
const CostPage = lazy(() =>
  import('../../features/cost/components/CostPage').then((m) => ({
    default: m.CostPage,
  }))
);
const SessionListPage = lazy(() =>
  import('../../features/auth/components/SessionListPage').then((m) => ({
    default: m.SessionListPage,
  }))
);
const ProfilePage = lazy(() =>
  import('../../features/auth/components/ProfilePage').then((m) => ({
    default: m.ProfilePage,
  }))
);
const PrivacyPage = lazy(() =>
  import('../../features/gdpr/components/PrivacyPage').then((m) => ({
    default: m.PrivacyPage,
  }))
);
const TenantSettingsPage = lazy(() =>
  import('../../features/tenants/components/TenantSettingsPage').then((m) => ({
    default: m.TenantSettingsPage,
  }))
);
const BaaSPage = lazy(() =>
  import('../../features/baas/components/BaaSPage').then((m) => ({ default: m.BaaSPage }))
);
const CustomerDetailPage = lazy(() =>
  import('../../features/baas/components/CustomerDetailPage').then((m) => ({ default: m.CustomerDetailPage }))
);
const BillingReportDetailPage = lazy(() =>
  import('../../features/baas/components/BillingReportDetailPage').then((m) => ({ default: m.BillingReportDetailPage }))
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
const MLModelDetailPage = lazy(() =>
  import('../../features/ml/components/MLModelDetailPage').then((m) => ({ default: m.MLModelDetailPage }))
);
const TrainingDashboardPage = lazy(() =>
  import('../../features/ml/components/TrainingDashboardPage').then((m) => ({ default: m.TrainingDashboardPage }))
);
const InferenceMetricsPage = lazy(() =>
  import('../../features/ml/components/InferenceMetricsPage').then((m) => ({ default: m.InferenceMetricsPage }))
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
const CommunitiesPage = lazy(() =>
  import('../../features/social/components/CommunitiesPage').then((m) => ({
    default: m.CommunitiesPage,
  }))
);
const TransformationPipelineListPage = lazy(() =>
  import('../../features/transformation/components/TransformationPipelineListPage').then((m) => ({
    default: m.TransformationPipelineListPage,
  }))
);
const TransformationPipelineDetailPage = lazy(() =>
  import('../../features/transformation/components/TransformationPipelineDetailPage').then((m) => ({
    default: m.TransformationPipelineDetailPage,
  }))
);
const TransformationPipelineCreatePage = lazy(() =>
  import('../../features/transformation/components/TransformationPipelineCreatePage').then((m) => ({
    default: m.TransformationPipelineCreatePage,
  }))
);
const TransformationRunDetailPage = lazy(() =>
  import('../../features/transformation/components/TransformationRunDetailPage').then((m) => ({
    default: m.TransformationRunDetailPage,
  }))
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
const CheckoutPage = lazy(() =>
  import('../../features/marketplace/components/CheckoutPage').then((m) => ({
    default: m.CheckoutPage,
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
const IntegrationsLayout = lazy(() =>
  import('../../features/integrations/components/IntegrationsLayout').then((m) => ({
    default: m.IntegrationsLayout,
  }))
);

// Lazy load heavy pages for code splitting
const AdminPage = lazy(() =>
  import('../../features/admin/components/AdminPage').then((m) => ({
    default: m.AdminPage,
  }))
);
const UserEditPage = lazy(() =>
  import('../../features/admin/components/UserEditPage').then((m) => ({
    default: m.UserEditPage,
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
  import('../pages/PlaceholderPages').then((m) => ({ default: m.ForbiddenPage }))
);

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/verify-email',
    element: <VerifyEmailPage />,
  },
  {
    path: '/auth/verify-email',
    element: <VerifyEmailPage />,
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
  // /onboard-org removed — org creation is now a Platform Admin function in /admin
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
    path: '/coming-soon',
    element: <ComingSoonPage />,
  },
  {
    path: '/403',
    element: (
      <EB fallbackMsg="Loading...">
        <ForbiddenPage />
      </EB>
    ),
  },
  {
    path: '/',
    element: <RootRoute />,
    children: [
      {
        index: true,
        element: (
          <EB fallbackMsg="Loading dashboard...">
            <HomePage />
          </EB>
        ),
      },
      {
        path: 'assets',
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading assets...">
                <AssetListPage />
              </EB>
            ),
          },
          {
            path: 'create',
            element: (
              <EB fallbackMsg="Loading...">
                <AssetCreatePage />
              </EB>
            ),
          },
          {
            path: ':id',
            element: (
              <EB fallbackMsg="Loading asset...">
                <AssetDetailPage />
              </EB>
            ),
          },
        ],
      },
      {
        path: 'datasets',
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading datasets...">
                <DatasetListPage />
              </EB>
            ),
          },
          {
            path: 'create',
            element: (
              <EB fallbackMsg="Loading...">
                <DatasetCreatePage />
              </EB>
            ),
          },
          {
            path: ':id',
            element: (
              <EB fallbackMsg="Loading dataset...">
                <DatasetDetailPage />
              </EB>
            ),
          },
          {
            path: ':id/versions',
            element: (
              <EB fallbackMsg="Loading versions...">
                <DatasetVersionsPage />
              </EB>
            ),
          },
        ],
      },
      {
        path: 'files',
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading files...">
                <FileListPage />
              </EB>
            ),
          },
        ],
      },
      {
        path: 'contracts',
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading contracts...">
                <ContractListPage />
              </EB>
            ),
          },
          {
            path: ':id',
            element: (
              <EB fallbackMsg="Loading contract...">
                <ContractDetailPage />
              </EB>
            ),
          },
          {
            path: ':id/edit',
            element: (
              <EB fallbackMsg="Loading contract editor...">
                <ContractEditorPage />
              </EB>
            ),
          },
          {
            path: ':id/link-odps',
            element: (
              <EB fallbackMsg="Loading...">
                <ODPSLinkPage />
              </EB>
            ),
          },
        ],
      },
      {
        path: 'marketplace',
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading marketplace...">
                <ListingListPage />
              </EB>
            ),
          },
          {
            path: 'listings/:id',
            element: (
              <EB fallbackMsg="Loading listing...">
                <ListingDetailPage />
              </EB>
            ),
          },
          {
            path: 'publish',
            element: (
              <EB fallbackMsg="Loading publish page...">
                <ListingPublishPage />
              </EB>
            ),
          },
          {
            path: 'checkout/:listingId',
            element: (
              <EB fallbackMsg="Loading checkout...">
                <CheckoutPage />
              </EB>
            ),
          },
          {
            path: 'orders',
            children: [
              {
                index: true,
                element: (
                  <EB fallbackMsg="Loading orders...">
                    <OrderListPage />
                  </EB>
                ),
              },
              {
                path: ':id',
                element: (
                  <EB fallbackMsg="Loading order...">
                    <OrderDetailPage />
                  </EB>
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
                  <EB fallbackMsg="Loading entitlements...">
                    <EntitlementListPage />
                  </EB>
                ),
              },
              {
                path: ':id',
                element: (
                  <EB fallbackMsg="Loading entitlement...">
                    <EntitlementDetailPage />
                  </EB>
                ),
              },
            ],
          },
        ],
      },
      {
        path: 'integrations',
        element: (
          <EB fallbackMsg="Loading...">
            <IntegrationsLayout />
          </EB>
        ),
        children: [
          {
            path: 'connections',
            children: [
              {
                index: true,
                element: (
                  <EB fallbackMsg="Loading connections...">
                    <MarketplaceConnectionListPage />
                  </EB>
                ),
              },
              {
                path: 'create',
                element: (
                  <EB fallbackMsg="Loading...">
                    <MarketplaceConnectionCreatePage />
                  </EB>
                ),
              },
              {
                path: ':id/edit',
                element: (
                  <EB fallbackMsg="Loading...">
                    <MarketplaceConnectionEditPage />
                  </EB>
                ),
              },
              {
                path: ':id',
                element: (
                  <EB fallbackMsg="Loading connection...">
                    <MarketplaceConnectionDetailPage />
                  </EB>
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
                  <EB fallbackMsg="Loading sync jobs...">
                    <MarketplaceSyncJobListPage />
                  </EB>
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
                  <EB fallbackMsg="Loading mappings...">
                    <MarketplaceMappingListPage />
                  </EB>
                ),
              },
              {
                // No mapping detail page exists yet — redirect unknown IDs to the list
                // so users see a sensible page instead of a blank outlet.
                path: ':id',
                element: <Navigate to="/integrations/mappings" replace />,
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
            element: <EB fallbackMsg="Loading ODPS..."><ODPSListPage /></EB>,
          },
          {
            path: 'upload',
            element: <EB fallbackMsg="Loading..."><ODPSUploadPage /></EB>,
          },
          {
            path: ':id',
            element: <EB fallbackMsg="Loading ODPS..."><ODPSDetailPage /></EB>,
          },
        ],
      },
      {
        path: 'dq',
        children: [
          {
            index: true,
            element: <EB fallbackMsg="Loading..."><DQRunListPage /></EB>,
          },
          {
            path: 'runs/:id',
            element: <EB fallbackMsg="Loading..."><DQRunDetailPage /></EB>,
          },
        ],
      },
      {
        path: 'compliance',
        children: [
          {
            index: true,
            element: <EB fallbackMsg="Loading..."><ComplianceRunListPage /></EB>,
          },
          {
            path: 'runs/:id',
            element: <EB fallbackMsg="Loading..."><ComplianceRunDetailPage /></EB>,
          },
        ],
      },
      {
        path: 'mesh',
        element: <MeshPage />,
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading mesh domains...">
                <MeshDomainListPage />
              </EB>
            ),
          },
          {
            path: 'topology',
            element: (
              <EB fallbackMsg="Loading topology...">
                <TopologyVisualization />
              </EB>
            ),
          },
          {
            path: 'create',
            element: (
              <EB fallbackMsg="Loading create form...">
                <MeshDomainCreatePage />
              </EB>
            ),
          },
          {
            path: ':id',
            element: (
              <EB fallbackMsg="Loading domain...">
                <MeshDomainDetailPage />
              </EB>
            ),
          },
        ],
      },
      {
        path: 'virtualization',
        element: <VirtualizationPage />,
        children: [
          { index: true, element: <EB fallbackMsg="Loading..."><VirtualDatasetListPage /></EB> },
          { path: 'create', element: <EB fallbackMsg="Loading..."><VirtualDatasetCreatePage /></EB> },
          { path: ':id/edit', element: <EB fallbackMsg="Loading..."><VirtualDatasetEditPage /></EB> },
          { path: ':id', element: <EB fallbackMsg="Loading..."><VirtualDatasetDetailPage /></EB> },
        ],
      },
      {
        path: 'search',
        element: <EB fallbackMsg="Loading..."><SearchPage /></EB>,
      },
      {
        path: 'semantic',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="semantic.sparql">
              <SemanticPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'ai/search',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="ai.natural-language-search">
              <AISearchPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'ai/schema-matching',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="ai.schema-matching">
              <SchemaMatchingPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        // Convenience alias: /sync-jobs → /integrations/sync-jobs (route is nested under integrations)
        path: 'sync-jobs',
        element: <Navigate to="/integrations/sync-jobs" replace />,
      },
      {
        path: 'social',
        element: <Navigate to="/communities" replace />,
      },
      {
        path: 'communities',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="social.communities">
              <CommunitiesPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'developer',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="developer.plugins">
              <DeveloperPortalPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'baas',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="baas.api-keys">
              <BaaSPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'baas/customers/:customerId',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="baas.api-keys">
              <CustomerDetailPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'baas/billing-reports/:reportId',
        element: (
          <ErrorBoundary>
            <CapabilityRoute capability="baas.api-keys">
              <BillingReportDetailPage />
            </CapabilityRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'ml',
        children: [
          {
            index: true,
            element: (
              <ErrorBoundary>
                <CapabilityRoute capability="ml.models">
                  <MLPage />
                </CapabilityRoute>
              </ErrorBoundary>
            ),
          },
          {
            path: 'models/:id',
            element: (
              <ErrorBoundary>
                <CapabilityRoute capability="ml.models">
                  <MLModelDetailPage />
                </CapabilityRoute>
              </ErrorBoundary>
            ),
          },
          {
            path: 'training/:id',
            element: (
              <ErrorBoundary>
                <CapabilityRoute capability="ml.models">
                  <TrainingDashboardPage />
                </CapabilityRoute>
              </ErrorBoundary>
            ),
          },
          {
            path: 'inference/:id',
            element: (
              <ErrorBoundary>
                <CapabilityRoute capability="ml.models">
                  <InferenceMetricsPage />
                </CapabilityRoute>
              </ErrorBoundary>
            ),
          },
        ],
      },
      {
        path: 'observability',
        element: (
          <EB fallbackMsg="Loading observability...">
            <ObservabilityPage />
          </EB>
        ),
      },
      {
        path: 'jobs',
        children: [
          {
            index: true,
            element: <EB fallbackMsg="Loading..."><JobListPage /></EB>,
          },
          {
            path: ':id',
            element: <EB fallbackMsg="Loading..."><JobDetailPage /></EB>,
          },
        ],
      },
      {
        path: 'transformation',
        element: (
          <CapabilityRoute capability="transformation">
            <EB fallbackMsg="Loading...">
              <Outlet />
            </EB>
          </CapabilityRoute>
        ),
        children: [
          { index: true, element: <EB fallbackMsg="Loading..."><TransformationPipelineListPage /></EB> },
          { path: 'create', element: <EB fallbackMsg="Loading..."><TransformationPipelineCreatePage /></EB> },
          { path: 'pipelines/:id', element: <EB fallbackMsg="Loading..."><TransformationPipelineDetailPage /></EB> },
          { path: 'executions/:id', element: <EB fallbackMsg="Loading..."><TransformationRunDetailPage /></EB> },
        ],
      },
      {
        path: 'webhooks',
        children: [
          {
            index: true,
            element: <EB fallbackMsg="Loading..."><WebhookListPage /></EB>,
          },
          {
            path: 'create',
            element: <EB fallbackMsg="Loading..."><WebhookCreatePage /></EB>,
          },
          {
            path: ':id',
            element: <EB fallbackMsg="Loading..."><WebhookDetailPage /></EB>,
          },
          {
            path: ':id/edit',
            element: <EB fallbackMsg="Loading..."><WebhookEditPage /></EB>,
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
          { index: true, element: <EB fallbackMsg="Loading..."><AccessRequestListPage /></EB> },
          { path: 'access-requests/create', element: <EB fallbackMsg="Loading..."><AccessRequestCreatePage /></EB> },
          { path: 'access-requests/:id', element: <EB fallbackMsg="Loading..."><AccessRequestDetailPage /></EB> },
          { path: 'retention', element: <EB fallbackMsg="Loading..."><RetentionPolicyListPage /></EB> },
          { path: 'retention/new', element: <EB fallbackMsg="Loading..."><RetentionPolicyCreatePage /></EB> },
          { path: 'retention/:id', element: <EB fallbackMsg="Loading..."><RetentionPolicyDetailPage /></EB> },
          { path: 'retention/:id/edit', element: <EB fallbackMsg="Loading..."><RetentionPolicyEditPage /></EB> },
        ],
      },
      {
        path: 'audit',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['AUDITOR', 'PLATFORM_ADMIN']}>
              <AuditEventListPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'audit/:id',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['AUDITOR', 'PLATFORM_ADMIN']}>
              <AuditEventDetailPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-ingestions',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledIngestionListPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-ingestions/create',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledIngestionCreatePage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-ingestions/:id',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledIngestionDetailPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-ingestions/:id/edit',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledIngestionEditPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-exports',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledExportListPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-exports/create',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledExportCreatePage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-exports/:id',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledExportDetailPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-exports/:id/edit',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
              <ScheduledExportEditPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'admin',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading admin...">
              <AdminPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        path: 'admin/users/:id/edit',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading...">
              <UserEditPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        path: 'settings',
        children: [
          {
            path: 'profile',
            element: (
              <EB fallbackMsg="Loading profile...">
                <ProfilePage />
              </EB>
            ),
          },
          {
            path: 'sessions',
            element: (
              <EB fallbackMsg="Loading sessions...">
                <SessionListPage />
              </EB>
            ),
          },
          {
            path: 'privacy',
            element: (
              <EB fallbackMsg="Loading privacy...">
                <PrivacyPage />
              </EB>
            ),
          },
          {
            path: 'api-keys',
            element: (
              <EB fallbackMsg="Loading API keys...">
                <AuthAPIKeyListPage />
              </EB>
            ),
          },
          {
            path: 'tenant',
            element: (
              <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <EB fallbackMsg="Loading tenant settings...">
                  <TenantSettingsPage />
                </EB>
              </ProtectedRoute>
            ),
          },
          {
            path: 'subscription',
            element: (
              <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <EB fallbackMsg="Loading subscription...">
                  <SubscriptionPage />
                </EB>
              </ProtectedRoute>
            ),
          },
          {
            path: 'cost',
            element: (
              <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <EB fallbackMsg="Loading cost tracking...">
                  <CostPage />
                </EB>
              </ProtectedRoute>
            ),
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: (
      <EB fallbackMsg="Loading...">
        <NotFoundPage />
      </EB>
    ),
  },
]);
