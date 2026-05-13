/**
 * Application Routes
 * Defines all routes with protection and capability gating
 */
/* eslint-disable react-refresh/only-export-components */

import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, Outlet, useParams } from 'react-router-dom';

/** Redirect /odps/:id → /contracts/:id (backward compat) */
function OdpsIdRedirect() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/contracts/${id}`} replace />;
}
// Critical routes - eagerly loaded (login, public pages)
import { AcceptInvitationPage } from '../../features/auth/components/AcceptInvitationPage';
import { LoginPage } from '../../features/auth/components/LoginPage';
import { VerifyEmailPage } from '../../features/auth/components/VerifyEmailPage';
// OrgOnboardingPage removed — org creation is now a Platform Admin function in /admin
import { PasswordResetConfirmPage } from '../../features/auth/components/PasswordResetConfirmPage';
import { PasswordResetPage } from '../../features/auth/components/PasswordResetPage';
import { PublicResourcesPage } from '../../features/auth/components/PublicResourcesPage';
import {
  PublicLayout,
  PublicLegalHomePage,
  PublicPrivacyNoticePage,
  PublicSubprocessorsPage,
  PublicPlatformDpiaSummaryPage,
} from '../../features/public';
import { RegisterPage } from '../../features/auth/components/RegisterPage';
import { RegistrationRoute } from '../../features/auth/components/RegistrationRoute';
import { RootRoute } from './RootRoute';
import { CapabilityRoute } from '../../shared/components/CapabilityRoute';
import { MvpGatedRoute } from '../../shared/components/MvpGatedRoute';
import { isMvpModeEnabledFromEnv } from '../../features/shell/utils/mvpNav';
import { COMPLIANCE_SIDEBAR_REQUIRED_ROLES } from '../../features/shell/utils/navItems';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { LoadingSpinner } from '../../shared/components/LoadingSpinner';
import { ProtectedRoute } from '../../shared/components/ProtectedRoute';
import { ComingSoonPage } from '../../shared/components/ComingSoonPage';
import { UnavailablePage } from '../../shared/components/UnavailablePage';
// Phase 250.6.A.5 — generic disabled-capability landing page,
// the redirect target for ``<CapabilityRoute capability="...">``.
// Reusable across capabilities (NOT hardcoded to asset_creation).
import { DisabledCapabilityPage } from '../../shared/components/DisabledCapabilityPage';

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
// Phase 260.4.H — admin audit-log search (TENANT_ADMIN-only)
const AdminAuditLogPage = lazy(() =>
  import('../../features/audit/components/AdminAuditLogPage').then((m) => ({
    default: m.AdminAuditLogPage,
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
const ProviderRevenuePage = lazy(() =>
  import(
    '../../features/billing/components/ProviderRevenuePage'
  ).then((m) => ({ default: m.ProviderRevenuePage }))
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
const RopaListPage = lazy(() =>
  import('../../features/ropa/components/RopaListPage').then((m) => ({
    default: m.RopaListPage,
  }))
);
const TenantSettingsPage = lazy(() =>
  import('../../features/tenants/components/TenantSettingsPage').then((m) => ({
    default: m.TenantSettingsPage,
  }))
);
const DelegationSettingsPage = lazy(() =>
  import(
    '../../features/governance/components/DelegationSettingsPage'
  ).then((m) => ({ default: m.DelegationSettingsPage }))
);
// Phase 228.F3.14 — Lineage subscriptions management page.
const LineageSubscriptionsPage = lazy(() =>
  import('../../features/contracts/components/LineageSubscriptionsPage').then((m) => ({
    default: m.LineageSubscriptionsPage,
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
const LineageEditPage = lazy(() =>
  import('../../features/contracts/components/LineageEditPage').then((m) => ({
    default: m.LineageEditPage,
  })),
);
const ContractEditorPage = lazy(() =>
  import('../../features/contracts/components/ContractEditorPage').then((m) => ({
    default: m.ContractEditorPage,
  }))
);
const ContractCreatePage = lazy(() =>
  import('../../features/contracts/components/ContractCreatePage').then((m) => ({
    default: m.ContractCreatePage,
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
// Phase 240.4.A.8 — advanced DQ feature routes.
const AnomaliesDashboard = lazy(() =>
  import('../../features/dq/components/AnomaliesDashboard').then((m) => ({
    default: m.AnomaliesDashboard,
  }))
);
const TrendsVisualization = lazy(() =>
  import('../../features/dq/components/TrendsVisualization').then((m) => ({
    default: m.TrendsVisualization,
  }))
);
const ScorecardsExecutiveDashboard = lazy(() =>
  import('../../features/dq/components/ScorecardsExecutiveDashboard').then((m) => ({
    default: m.ScorecardsExecutiveDashboard,
  }))
);
const AlertingRuleManager = lazy(() =>
  import('../../features/dq/components/AlertingRuleManager').then((m) => ({
    default: m.AlertingRuleManager,
  }))
);
const RootCauseAnalysisPage = lazy(() =>
  import('../../features/dq/components/RootCauseAnalysisPage').then((m) => ({
    default: m.RootCauseAnalysisPage,
  }))
);
const FileListPage = lazy(() =>
  import('../../features/files/components/FileListPage').then((m) => ({ default: m.FileListPage }))
);
// Phase 260.4.B — dedicated /files/:id detail page (replaces the
// modal as the primary surface; deep-linkable + room for the audit
// log section).
const FileDetailPage = lazy(() =>
  import('../../features/files/components/FileDetailPage').then((m) => ({
    default: m.FileDetailPage,
  })),
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
const RetentionDashboardPage = lazy(() =>
  import('../../features/governance/components/RetentionDashboardPage').then((m) => ({
    default: m.RetentionDashboardPage,
  }))
);
const PurposeManagerPage = lazy(() =>
  import('../../features/governance/components/PurposeManagerPage').then((m) => ({
    default: m.PurposeManagerPage,
  }))
);
const ConsentDashboardPage = lazy(() =>
  import('../../features/governance/components/ConsentDashboardPage').then((m) => ({
    default: m.ConsentDashboardPage,
  }))
);
const PublicDsarSubmitPage = lazy(() =>
  import('../../features/dsar/components/PublicDsarSubmitPage').then((m) => ({
    default: m.PublicDsarSubmitPage,
  }))
);
const PublicDsarStatusPage = lazy(() =>
  import('../../features/dsar/components/PublicDsarStatusPage').then((m) => ({
    default: m.PublicDsarStatusPage,
  }))
);
const DsarQueuePage = lazy(() =>
  import('../../features/dsar/components/DsarQueuePage').then((m) => ({
    default: m.DsarQueuePage,
  }))
);
const DsarDetailPage = lazy(() =>
  import('../../features/dsar/components/DsarDetailPage').then((m) => ({
    default: m.DsarDetailPage,
  }))
);
const BreachDashboardPage = lazy(() =>
  import('../../features/breach/components/BreachDashboardPage').then((m) => ({
    default: m.BreachDashboardPage,
  }))
);
const BreachDetailPage = lazy(() =>
  import('../../features/breach/components/BreachDetailPage').then((m) => ({
    default: m.BreachDetailPage,
  }))
);
const ReportBreachPage = lazy(() =>
  import('../../features/breach/components/ReportBreachPage').then((m) => ({
    default: m.ReportBreachPage,
  }))
);
const BreachTemplateEditorPage = lazy(() =>
  import('../../features/breach/components/BreachTemplateEditorPage').then((m) => ({
    default: m.BreachTemplateEditorPage,
  }))
);
const ProcessorAgreementsPage = lazy(() =>
  import('../../features/processorAgreements/components/ProcessorAgreementsPage').then((m) => ({
    default: m.ProcessorAgreementsPage,
  }))
);
const DpiaWizardPage = lazy(() =>
  import('../../features/dpia/components/DpiaWizardPage').then((m) => ({
    default: m.DpiaWizardPage,
  }))
);
const DpiaReviewQueuePage = lazy(() =>
  import('../../features/dpia/components/DpiaReviewQueuePage').then((m) => ({
    default: m.DpiaReviewQueuePage,
  }))
);
const DpiaReviewPage = lazy(() =>
  import('../../features/dpia/components/DpiaReviewPage').then((m) => ({
    default: m.DpiaReviewPage,
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
const ContractLinkODPSPage = lazy(() =>
  import('../../features/contracts/components/ContractLinkODPSPage').then((m) => ({ default: m.ContractLinkODPSPage }))

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

const NotificationListPage = lazy(() =>
  import('../../features/notifications/components/NotificationListPage').then((m) => ({
    default: m.NotificationListPage,
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
// Phase 227 Wave 1 (227.L5.8) — TENANT_ADMIN structureless triage page.
const ContractHealthPage = lazy(() =>
  import('../../features/admin/components/ContractHealthPage').then((m) => ({
    default: m.ContractHealthPage,
  })),
);

const AdminPage = lazy(() =>
  import('../../features/admin/components/AdminPage').then((m) => ({
    default: m.AdminPage,
  }))
);
const KYBReviewQueuePage = lazy(() =>
  import(
    '../../features/admin/components/KYBReviewQueuePage'
  ).then((m) => ({ default: m.KYBReviewQueuePage }))
);

// Phase 228 F4 (228.F4.19) — OpenLineage admin route.
// Two side-by-side panels: ingest-key management + ops status.
const OpenLineageAdminPage = lazy(async () => {
  const [{ OpenLineageKeyManagement }, { OpenLineageStatusPanel }] = await Promise.all([
    import('../../features/admin/components/openlineage/OpenLineageKeyManagement'),
    import('../../features/admin/components/openlineage/OpenLineageStatusPanel'),
  ]);
  return {
    default: () => (
      <div className="openlineage-admin-page">
        <OpenLineageKeyManagement />
        <OpenLineageStatusPanel />
      </div>
    ),
  };
});
const UserEditPage = lazy(() =>
  import('../../features/admin/components/UserEditPage').then((m) => ({
    default: m.UserEditPage,
  }))
);
// Phase 250.6.E.1 — per-tenant feature-flags admin page.
const TenantFeatureFlagsAdminPage = lazy(() =>
  import('../../features/admin/components/TenantFeatureFlagsAdminPage').then(
    (m) => ({
      default: m.TenantFeatureFlagsAdminPage,
    }),
  ),
);
// Phase 235.1 — PLATFORM_ADMIN cross-tenant feature-flag UI (registry-driven).
// Distinct from TenantFeatureFlagsAdminPage (which is the TENANT_ADMIN
// self-service surface): this page targets ANY tenant from a PLATFORM_ADMIN
// session and routes through the new /api/v1/admin/tenants/{id}/feature-flags/
// endpoint with the two-person-rule on sensitive flags.
const FeatureFlagPage = lazy(() =>
  import('../../features/admin/components/FeatureFlagPage').then((m) => ({
    default: m.FeatureFlagPage,
  })),
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

// Track A PR 3: extracted to a named export so the drift test in
// frontend/src/app/routes/mvpGateDrift.test.tsx (PR 4) can walk the
// route tree and assert every NON_MVP_PATHS entry has a <MvpGatedRoute>
// wrapper. Production code uses the same array via createBrowserRouter
// below — single source of truth.
export const appRoutes: Parameters<typeof createBrowserRouter>[0] = [
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
    path: '/legal',
    element: <PublicLayout />,
    children: [
      { index: true, element: <PublicLegalHomePage /> },
      { path: 'privacy', element: <PublicPrivacyNoticePage /> },
      { path: 'subprocessors', element: <PublicSubprocessorsPage /> },
      { path: 'dpia', element: <PublicPlatformDpiaSummaryPage /> },
      {
        path: 'dsar',
        element: (
          <EB fallbackMsg="Loading…">
            <PublicDsarSubmitPage />
          </EB>
        ),
      },
      {
        path: 'dsar/status/:referenceToken',
        element: (
          <EB fallbackMsg="Loading…">
            <PublicDsarStatusPage />
          </EB>
        ),
      },
    ],
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
    // Phase 250.6.A.5 — `/unavailable` is the redirect target for
    // ``<CapabilityRoute>`` when the required capability is False.
    // Replaced the legacy ``<UnavailablePage>`` with the new
    // ``<DisabledCapabilityPage>`` which (a) reads the capability
    // name from `location.state.capability` (set by CapabilityRoute),
    // (b) renders capability-specific copy when available, (c)
    // surfaces the capability key for support tickets, (d) provides
    // a "back to dashboard" CTA. The legacy ``UnavailablePage`` is
    // preserved as an import for any direct callers but is no longer
    // wired into the route table.
    path: '/unavailable',
    element: <DisabledCapabilityPage />,
  },
  {
    // Legacy alias for direct callers that still navigate to
    // `/feature-unavailable`. Routes to the same surface so the
    // redirect path is consistent.
    path: '/feature-unavailable',
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
            // Phase 250.6.A.2 (D250.17) — wrap /assets/create in
            // BOTH route gates so the URL is consistent with the
            // sidebar nav AND with the per-tenant kill switch:
            //   * <MvpGatedRoute> — redirects to /coming-soon when
            //     the deploy is in MVP_MODE and the path is gated
            //     by mvpNav.ts (matches the sidebar gating).
            //   * <CapabilityRoute capability="asset_creation"> —
            //     redirects to /unavailable when the per-tenant
            //     ``asset_creation`` capability (mirrored from
            //     ``Tenant.asset_creation_enabled``) is False.
            // The order is MvpGatedRoute → CapabilityRoute so MVP
            // gating wins when both apply (the MVP gate is a
            // platform-wide release control; capability is a
            // per-tenant runtime control).
            path: 'create',
            element: (
              <EB fallbackMsg="Loading...">
                <MvpGatedRoute>
                  <CapabilityRoute capability="asset_creation">
                    <AssetCreatePage />
                  </CapabilityRoute>
                </MvpGatedRoute>
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
        // Phase 260.3.B.2 — ``MvpGatedRoute`` + ``CapabilityRoute`` (order matches
        // /assets/create and /dq). Pass-through in MVP when path is not in
        // NON_MVP_PATHS; tenant kill-switch uses capability keys ``datasets`` /
        // ``files`` from ``GET /api/v1/capabilities/``.
        path: 'datasets',
        element: (
          <MvpGatedRoute>
            <CapabilityRoute capability="datasets">
              <Outlet />
            </CapabilityRoute>
          </MvpGatedRoute>
        ),
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
        element: (
          <MvpGatedRoute>
            <CapabilityRoute capability="files">
              <Outlet />
            </CapabilityRoute>
          </MvpGatedRoute>
        ),
        children: [
          {
            index: true,
            element: (
              <EB fallbackMsg="Loading files...">
                <FileListPage />
              </EB>
            ),
          },
          {
            // Phase 260.4.B — file detail page; deep-linkable surface.
            path: ':id',
            element: (
              <EB fallbackMsg="Loading file...">
                <FileDetailPage />
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
            path: 'create',
            element: (
              <EB fallbackMsg="Loading contract creator...">
                <ContractCreatePage />
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
            // Phase 228.F2.16 — field-level lineage editor.
            path: ':id/lineage/edit',
            element: (
              <EB fallbackMsg="Loading lineage editor...">
                <LineageEditPage />
              </EB>
            ),
          },
          {
            path: ':id/link-odps',
            element: (
              <EB fallbackMsg="Loading...">
                <ContractLinkODPSPage />
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
          <MvpGatedRoute>
            <EB fallbackMsg="Loading...">
              <IntegrationsLayout />
            </EB>
          </MvpGatedRoute>
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
        // Backward-compat redirects: /odps/* → /contracts/* (Phase 211.A6)
        path: 'odps',
        children: [
          {
            index: true,
            element: <Navigate to="/contracts?spec_type=ODPS" replace />,
          },
          {
            path: 'upload',
            element: <Navigate to="/contracts/create" replace />,
          },
          {
            path: ':id',
            element: <OdpsIdRedirect />,
          },
        ],
      },
      {
        // Phase 240.4.B.3 — wrap the entire /dq subtree in
        // ``MvpGatedRoute`` (matches the existing pattern for other
        // MVP-gated features) AND ``CapabilityRoute capability="data_quality"``.
        // The capability is sourced from ``Tenant.data_quality_enabled``
        // via ``GET /api/v1/capabilities/`` (see Phase 240.4.B.4) — the
        // SPA never navigates to /dq/* when the tenant has the feature
        // disabled, complementing the backend's HTTP 403 +
        // DATA_QUALITY_DISABLED gate from Phase 240.4.B.2.
        path: 'dq',
        element: (
          <MvpGatedRoute>
            <CapabilityRoute capability="data_quality">
              <Outlet />
            </CapabilityRoute>
          </MvpGatedRoute>
        ),
        children: [
          {
            index: true,
            element: <EB fallbackMsg="Loading..."><DQRunListPage /></EB>,
          },
          {
            path: 'runs/:id',
            element: <EB fallbackMsg="Loading..."><DQRunDetailPage /></EB>,
          },
          // Phase 240.4.A.8 — advanced DQ feature routes.
          //
          // Phase 240.4.B.3 — each advanced sub-route is additionally
          // wrapped in ``CapabilityRoute capability="data_quality_advanced"``.
          // The advanced capability is conjunctive on the wire (per
          // Phase 240.4.B.4: ``data_quality_advanced = base AND advanced``)
          // so the wrapper denies access whenever EITHER flag is off.
          {
            path: 'anomalies',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><AnomaliesDashboard /></EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'trends',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><TrendsVisualization /></EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'scorecards',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><ScorecardsExecutiveDashboard /></EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'alerting-rules',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><AlertingRuleManager /></EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'rca',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><RootCauseAnalysisPage /></EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'runs/:id/rca',
            element: (
              <CapabilityRoute capability="data_quality_advanced">
                <EB fallbackMsg="Loading..."><RootCauseAnalysisPage /></EB>
              </CapabilityRoute>
            ),
          },
        ],
      },
      {
        path: 'compliance',
        element: (
          <ProtectedRoute requiredRole={[...COMPLIANCE_SIDEBAR_REQUIRED_ROLES]}>
            <Outlet />
          </ProtectedRoute>
        ),
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
        element: (
          <MvpGatedRoute>
            <MeshPage />
          </MvpGatedRoute>
        ),
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
        element: (
          <MvpGatedRoute>
            <VirtualizationPage />
          </MvpGatedRoute>
        ),
        children: [
          { index: true, element: <EB fallbackMsg="Loading..."><VirtualDatasetListPage /></EB> },
          { path: 'create', element: <EB fallbackMsg="Loading..."><VirtualDatasetCreatePage /></EB> },
          { path: ':id/edit', element: <EB fallbackMsg="Loading..."><VirtualDatasetEditPage /></EB> },
          { path: ':id', element: <EB fallbackMsg="Loading..."><VirtualDatasetDetailPage /></EB> },
        ],
      },
      {
        path: 'search',
        element: (
          <EB fallbackMsg="Loading..."><SearchPage /></EB>
        ),
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
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="ai.natural-language-search">
                <AISearchPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'ai/schema-matching',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="ai.schema-matching">
                <SchemaMatchingPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        // Convenience alias: /sync-jobs → /integrations/sync-jobs (route is nested under integrations)
        path: 'sync-jobs',
        element: <Navigate to="/integrations/sync-jobs" replace />,
      },
      {
        // Track A PR 3: in MVP mode, /social used to redirect to
        // /communities (also non-MVP), pushing the user to a gated page
        // that itself redirects to /coming-soon. Short-circuit to
        // /coming-soon directly. The flag is build-time inlined, so
        // this evaluates to a constant per deploy.
        path: 'social',
        element: isMvpModeEnabledFromEnv() ? (
          <Navigate to="/coming-soon" replace />
        ) : (
          <Navigate to="/communities" replace />
        ),
      },
      {
        path: 'communities',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="social.communities">
                <CommunitiesPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'developer',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="developer.plugins">
                <DeveloperPortalPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'baas',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="baas.api-keys">
                <BaaSPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'baas/customers/:customerId',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="baas.api-keys">
                <CustomerDetailPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'baas/billing-reports/:reportId',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <CapabilityRoute capability="baas.api-keys">
                <BillingReportDetailPage />
              </CapabilityRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'ml',
        // Track A PR 3: parent had no `element`, so children rendered
        // unwrapped. Add an Outlet wrapped in MvpGatedRoute so the gate
        // fires before any child route renders.
        element: (
          <MvpGatedRoute>
            <Outlet />
          </MvpGatedRoute>
        ),
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
          <MvpGatedRoute>
            <EB fallbackMsg="Loading observability...">
              <ObservabilityPage />
            </EB>
          </MvpGatedRoute>
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
          <MvpGatedRoute>
            <CapabilityRoute capability="transformation">
              <EB fallbackMsg="Loading...">
                <Outlet />
              </EB>
            </CapabilityRoute>
          </MvpGatedRoute>
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
          <ProtectedRoute
            requiredRole={['TENANT_ADMIN', 'DPO', 'LEGAL_ADMIN', 'SECURITY_ADMIN', 'PLATFORM_ADMIN']}
          >
            <GovernanceLayout />
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <EB fallbackMsg="Loading..."><AccessRequestListPage /></EB> },
          { path: 'access-requests/create', element: <EB fallbackMsg="Loading..."><AccessRequestCreatePage /></EB> },
          { path: 'access-requests/:id', element: <EB fallbackMsg="Loading..."><AccessRequestDetailPage /></EB> },
          {
            path: 'dsar-requests',
            element: (
              <EB fallbackMsg="Loading...">
                <DsarQueuePage />
              </EB>
            ),
          },
          {
            path: 'dsar-requests/:id',
            element: (
              <EB fallbackMsg="Loading...">
                <DsarDetailPage />
              </EB>
            ),
          },
          { path: 'consent/purposes', element: <EB fallbackMsg="Loading..."><PurposeManagerPage /></EB> },
          { path: 'consent/dashboard', element: <EB fallbackMsg="Loading..."><ConsentDashboardPage /></EB> },
          {
            path: 'dpia/review-queue',
            element: (
              <CapabilityRoute capability="compliance_dpia">
                <EB fallbackMsg="Loading...">
                  <DpiaReviewQueuePage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'dpia/:dpiaId/review',
            element: (
              <CapabilityRoute capability="compliance_dpia">
                <EB fallbackMsg="Loading...">
                  <DpiaReviewPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'dpia/:dpiaId',
            element: (
              <CapabilityRoute capability="compliance_dpia">
                <EB fallbackMsg="Loading...">
                  <DpiaWizardPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'breach',
            element: (
              <CapabilityRoute capability="compliance_breach">
                <EB fallbackMsg="Loading...">
                  <BreachDashboardPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'breach/report',
            element: (
              <CapabilityRoute capability="compliance_breach">
                <EB fallbackMsg="Loading...">
                  <ReportBreachPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'breach/templates',
            element: (
              <CapabilityRoute capability="compliance_breach">
                <EB fallbackMsg="Loading...">
                  <BreachTemplateEditorPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'breach/:id',
            element: (
              <CapabilityRoute capability="compliance_breach">
                <EB fallbackMsg="Loading...">
                  <BreachDetailPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'processor-agreements',
            element: (
              <CapabilityRoute capability="compliance_processor_agreements">
                <EB fallbackMsg="Loading...">
                  <ProcessorAgreementsPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          {
            path: 'retention/dashboard',
            element: (
              <CapabilityRoute capability="compliance_retention_enforcer">
                <EB fallbackMsg="Loading...">
                  <RetentionDashboardPage />
                </EB>
              </CapabilityRoute>
            ),
          },
          { path: 'retention', element: <EB fallbackMsg="Loading..."><RetentionPolicyListPage /></EB> },
          { path: 'retention/new', element: <EB fallbackMsg="Loading..."><RetentionPolicyCreatePage /></EB> },
          { path: 'retention/:id', element: <EB fallbackMsg="Loading..."><RetentionPolicyDetailPage /></EB> },
          { path: 'retention/:id/edit', element: <EB fallbackMsg="Loading..."><RetentionPolicyEditPage /></EB> },
        ],
      },
      {
        path: 'notifications',
        element: (
          <EB fallbackMsg="Loading notifications...">
            <NotificationListPage />
          </EB>
        ),
      },
      {
        // Phase 234.2 — TENANT_ADMIN gains UI access to /audit.
        // Backend ``AUDIT_READ_ROLES`` (hub/apps/audit/views.py) has
        // always allowed TENANT_ADMIN through the API. Without the
        // matching frontend role, the tenant admin had the data via
        // ``GET /api/v1/audit/audit-events/`` but no UI to view it —
        // surfaced as a /403 redirect from this guard. Aligning the
        // two allow-lists closes the gap; ``auditRouteAccess.test.tsx``
        // pins the contract so a future drift in either direction
        // fails CI before reaching staging.
        path: 'audit',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['TENANT_ADMIN', 'AUDITOR', 'PLATFORM_ADMIN']}>
              <AuditEventListPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'audit/:id',
        element: (
          <ErrorBoundary>
            <ProtectedRoute requiredRole={['TENANT_ADMIN', 'AUDITOR', 'PLATFORM_ADMIN']}>
              <AuditEventDetailPage />
            </ProtectedRoute>
          </ErrorBoundary>
        ),
      },
      {
        path: 'scheduled-ingestions',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledIngestionListPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/create',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledIngestionCreatePage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/:id',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledIngestionDetailPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-ingestions/:id/edit',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledIngestionEditPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-exports',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledExportListPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-exports/create',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledExportCreatePage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-exports/:id',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledExportDetailPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
        ),
      },
      {
        path: 'scheduled-exports/:id/edit',
        element: (
          <MvpGatedRoute>
            <ErrorBoundary>
              <ProtectedRoute requiredRole={['DATA_PROVIDER', 'TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <ScheduledExportEditPage />
              </ProtectedRoute>
            </ErrorBoundary>
          </MvpGatedRoute>
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
        // Phase 250.6.E.1 — per-tenant feature-flags admin page.
        // TENANT_ADMIN-only per Phase 250.6.E.2 — the
        // ``<ProtectedRoute>`` gate matches the convention used by
        // the other admin/* routes (admin, contract-health,
        // openlineage). The backend endpoints
        // ``GET/PATCH /api/v1/tenants/me/feature-flags/`` AND
        // ``GET /api/v1/tenants/me/feature-flag-history/`` ALSO
        // enforce the role gate via ``_enforce_tenant_admin`` —
        // the FE gate is a UX-grade convenience (don't render the
        // page for non-admins) layered on top of the load-bearing
        // backend gate (don't accept the request from non-admins).
        path: 'admin/tenant-settings',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading tenant settings...">
              <TenantFeatureFlagsAdminPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        // Phase 235.1 — PLATFORM_ADMIN cross-tenant feature-flag UI.
        // Distinct from /admin/tenant-settings (TENANT_ADMIN self-
        // service): this route targets ANY tenant and routes through
        // the new admin endpoint with the two-person rule on
        // sensitive flags.
        path: 'admin/feature-flags',
        element: (
          <ProtectedRoute requiredRole={['PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading feature flags...">
              <FeatureFlagPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        // Phase 227 Wave 1 (227.L5.8) — TENANT_ADMIN structureless-
        // contract triage page. Lists contracts whose normalised
        // payload has no resolvable models or schema fields with
        // per-row deep-links into the Schema editor.
        path: 'admin/contract-health',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading contract health...">
              <ContractHealthPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        // Phase 260.4.H — TENANT_ADMIN-only audit log search.
        // Accepts ``?resource_type=...&resource_id=...`` query params
        // for deep-linking from detail pages (e.g. "View audit
        // history" CTA on a file detail page would land here with
        // ``?resource_type=FILE&resource_id={id}``). The backend's
        // raw audit endpoint already requires TENANT_ADMIN /
        // AUDITOR / PLATFORM_ADMIN; this route gate is the FE
        // affordance so a regular user never sees a link to a
        // page that 403s.
        path: 'admin/audit-log',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading audit log...">
              <AdminAuditLogPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        // Phase 228 F4 (228.F4.19) — OpenLineage admin route.
        // Hosts ``OpenLineageKeyManagement`` (key list / create /
        // revoke) + ``OpenLineageStatusPanel`` (DLQ + delivery
        // counts). Capability-flag gated server-side; the UI
        // surfaces a 404 from the backend gracefully.
        path: 'admin/integrations/openlineage',
        element: (
          <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading OpenLineage admin...">
              <OpenLineageAdminPage />
            </EB>
          </ProtectedRoute>
        ),
      },
      {
        // Phase 271.5.2 — PLATFORM_ADMIN KYB review queue for
        // Stripe Connect onboarding. Lists accounts stuck in
        // details_submitted=True && charges_enabled=False > 24h.
        path: 'admin/connect',
        element: (
          <ProtectedRoute requiredRole={['PLATFORM_ADMIN']}>
            <EB fallbackMsg="Loading KYB review queue...">
              <KYBReviewQueuePage />
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
            path: 'ropa',
            element: (
              <EB fallbackMsg="Loading RoPA...">
                <RopaListPage />
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
            // Phase 228.F3.14 (REQ-LIN-F3-006) — lineage-impact
            // subscriptions management.  Capability-gate happens
            // inside the page component so the route is reachable
            // even when the flag is off (for the "feature unavailable"
            // empty state).
            path: 'subscriptions',
            element: (
              <EB fallbackMsg="Loading lineage subscriptions...">
                <LineageSubscriptionsPage />
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
          {
            // Phase 272.6.7 — Approval delegation out-of-office coverage.
            path: 'delegation',
            element: (
              <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <EB fallbackMsg="Loading delegation settings...">
                  <DelegationSettingsPage />
                </EB>
              </ProtectedRoute>
            ),
          },
          {
            // Phase 271.4.3 — Stripe Connect provider revenue dashboard.
            // Lists payouts + status + arrival dates; surfaces
            // payout.failed events with a yellow alert banner.
            path: 'revenue',
            element: (
              <ProtectedRoute requiredRole={['TENANT_ADMIN', 'PLATFORM_ADMIN']}>
                <EB fallbackMsg="Loading revenue...">
                  <ProviderRevenuePage />
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
];

export const router = createBrowserRouter(appRoutes);
