/**
 * Route Configuration
 *
 * Main route configuration with code splitting and route guards.
 */

import React from 'react'
import { BrowserRouter, Routes } from 'react-router-dom'
import { renderRoute, createLazyRoute } from './utils'
import type { RouteConfig } from './types'

// Lazy-loaded pages with code splitting
const HomePage = createLazyRoute(() => import('@/pages/Home'))
const LoginPage = createLazyRoute(() => import('@/pages/auth/LoginPage'))
const RegisterPage = createLazyRoute(() => import('@/pages/auth/RegisterPage'))
const PasswordResetRequestPage = createLazyRoute(() => import('@/pages/auth/PasswordResetRequestPage'))
const PasswordResetConfirmPage = createLazyRoute(() => import('@/pages/auth/PasswordResetConfirmPage'))
const TenantSelectionPage = createLazyRoute(() => import('@/pages/auth/TenantSelectionPage'))
const ApiKeyManagementPage = createLazyRoute(() => import('@/pages/auth/ApiKeyManagementPage'))
const ActiveSessionsPage = createLazyRoute(() => import('@/pages/auth/ActiveSessionsPage'))
const UnauthorizedPage = createLazyRoute(() => import('@/pages/Unauthorized'))
const NotFoundPage = createLazyRoute(() => import('@/pages/NotFound'))
const AssetDetailPage = createLazyRoute(() => import('@/pages/assets/AssetDetailPage'))
const ContractDetailPage = createLazyRoute(() => import('@/pages/contracts/ContractDetailPage'))
const DatasetsPage = createLazyRoute(() => import('@/pages/datasets/DatasetsPage'))
const DatasetUploadPage = createLazyRoute(() => import('@/pages/datasets/DatasetUploadPage'))
const MarketplaceAssetDetailPage = createLazyRoute(() => import('@/pages/marketplace/MarketplaceAssetDetailPage'))
const DatasetDetailPage = createLazyRoute(() => import('@/pages/datasets/DatasetDetailPage'))
const ComplianceDashboardPage = createLazyRoute(() => import('@/pages/compliance/ComplianceDashboardPage'))
const ComplianceScanDetailPage = createLazyRoute(() => import('@/pages/compliance/ComplianceScanDetailPage'))
const DataQualityDashboardPage = createLazyRoute(() => import('@/pages/data-quality/DataQualityDashboardPage'))
const TenantAdminPage = createLazyRoute(() => import('@/pages/admin/tenant/TenantAdminPage'))
const ComplianceReportPage = createLazyRoute(() => import('@/pages/compliance/ComplianceReportPage'))

// Example lazy-loaded protected pages (can be expanded)
const AssetsPage = createLazyRoute(() => import('@/pages/assets/AssetsPage'))
const MarketplacePage = createLazyRoute(() => import('@/pages/marketplace/MarketplacePage'))
const APIDocumentationPage = createLazyRoute(() => import('@/pages/api-docs/APIDocumentationPage'))
const PlatformAdminPage = createLazyRoute(() => import('@/pages/admin/platform/PlatformAdminPage'))

/**
 * Route configuration
 * Routes are defined here with their guards and metadata
 */
export const routeConfig: RouteConfig[] = [
  // Public routes - Authentication
  {
    path: '/auth/login',
    element: <LoginPage />,
    label: 'Login',
    meta: {
      title: 'Login - Data Interoperability Hub',
    },
  },
  {
    path: '/login',
    element: <LoginPage />,
    label: 'Login',
    meta: {
      title: 'Login - Data Interoperability Hub',
    },
  },
  {
    path: '/auth/register',
    element: <RegisterPage />,
    label: 'Register',
    meta: {
      title: 'Register - Data Interoperability Hub',
    },
  },
  {
    path: '/auth/password-reset',
    element: <PasswordResetRequestPage />,
    label: 'Password Reset',
    meta: {
      title: 'Password Reset - Data Interoperability Hub',
    },
  },
  {
    path: '/auth/password-reset/confirm',
    element: <PasswordResetConfirmPage />,
    label: 'Confirm Password Reset',
    meta: {
      title: 'Confirm Password Reset - Data Interoperability Hub',
    },
  },
  {
    path: '/auth/tenant-selection',
    element: <TenantSelectionPage />,
    label: 'Select Tenant',
    requireAuth: true,
    meta: {
      title: 'Select Tenant - Data Interoperability Hub',
    },
  },
  {
    path: '/unauthorized',
    element: <UnauthorizedPage />,
    label: 'Unauthorized',
    meta: {
      title: 'Unauthorized - Data Interoperability Hub',
    },
  },

  // Protected routes
  {
    path: '/',
    element: <HomePage />,
    label: 'Home',
    requireAuth: true,
    meta: {
      title: 'Home - Data Interoperability Hub',
    },
  },
  {
    path: '/assets',
    element: <AssetsPage />,
    label: 'Assets',
    requireAuth: true,
    permissions: ['assets.view'],
    meta: {
      title: 'Assets - Data Interoperability Hub',
    },
  },
  {
    path: '/assets/:id',
    element: <AssetDetailPage />,
    label: 'Asset Detail',
    requireAuth: true,
    permissions: ['assets.view'],
    meta: {
      title: 'Asset Detail - Data Interoperability Hub',
    },
  },
  {
    path: '/contracts/:id',
    element: <ContractDetailPage />,
    label: 'Contract Detail',
    requireAuth: true,
    permissions: ['contracts.view'],
    meta: {
      title: 'Contract Detail - Data Interoperability Hub',
    },
  },
  {
    path: '/datasets',
    element: <DatasetsPage />,
    label: 'Datasets',
    requireAuth: true,
    permissions: ['datasets.view'],
    meta: {
      title: 'Datasets - Data Interoperability Hub',
    },
  },
  {
    path: '/datasets/:id',
    element: <DatasetDetailPage />,
    label: 'Dataset Detail',
    requireAuth: true,
    permissions: ['datasets.view'],
    meta: {
      title: 'Dataset Detail - Data Interoperability Hub',
    },
  },
  {
    path: '/datasets/new',
    element: <DatasetUploadPage />,
    label: 'Upload Dataset',
    requireAuth: true,
    permissions: ['datasets.create'],
    meta: {
      title: 'Upload Dataset - Data Interoperability Hub',
    },
  },
  {
    path: '/marketplace',
    element: <MarketplacePage />,
    label: 'Marketplace',
    requireAuth: true,
    permissions: ['marketplace.view'],
    meta: {
      title: 'Marketplace - Data Interoperability Hub',
    },
  },
  {
    path: '/marketplace/:id',
    element: <MarketplaceAssetDetailPage />,
    label: 'Marketplace Asset Detail',
    requireAuth: true,
    permissions: ['marketplace.view'],
    meta: {
      title: 'Marketplace Asset Detail - Data Interoperability Hub',
    },
  },
  {
    path: '/compliance',
    element: <ComplianceDashboardPage />,
    label: 'Compliance',
    requireAuth: true,
    permissions: ['compliance.view'],
    meta: {
      title: 'Compliance Dashboard - Data Interoperability Hub',
    },
  },
  {
    path: '/compliance/scans/:id',
    element: <ComplianceScanDetailPage />,
    label: 'Compliance Scan Detail',
    requireAuth: true,
    permissions: ['compliance.view'],
    meta: {
      title: 'Compliance Scan Detail - Data Interoperability Hub',
    },
  },
  {
    path: '/compliance/reports',
    element: <ComplianceReportPage />,
    label: 'Compliance Report',
    requireAuth: true,
    permissions: ['compliance.view'],
    meta: {
      title: 'Compliance Report - Data Interoperability Hub',
    },
  },
  {
    path: '/api-docs',
    element: <APIDocumentationPage />,
    label: 'API Documentation',
    requireAuth: false,
    meta: {
      title: 'API Documentation - Data Interoperability Hub',
    },
  },
  {
    path: '/data-quality',
    element: <DataQualityDashboardPage />,
    label: 'Data Quality',
    requireAuth: true,
    permissions: ['data_quality.view'],
    meta: {
      title: 'Data Quality Dashboard - Data Interoperability Hub',
    },
  },
  {
    path: '/admin/tenant',
    element: <TenantAdminPage />,
    label: 'Tenant Admin',
    requireAuth: true,
    roles: ['TENANT_ADMIN'],
    meta: {
      title: 'Tenant Administration - Data Interoperability Hub',
    },
  },

  // Protected routes - Settings
  {
    path: '/settings/api-keys',
    element: <ApiKeyManagementPage />,
    label: 'API Keys',
    requireAuth: true,
    meta: {
      title: 'API Key Management - Data Interoperability Hub',
    },
  },
  {
    path: '/settings/sessions',
    element: <ActiveSessionsPage />,
    label: 'Active Sessions',
    requireAuth: true,
    meta: {
      title: 'Active Sessions - Data Interoperability Hub',
    },
  },

  // Admin routes
  {
    path: '/admin',
    element: <HomePage />,
    label: 'Admin',
    requireAuth: true,
    roles: ['admin', 'platform_admin'],
    meta: {
      title: 'Admin - Data Interoperability Hub',
    },
    children: [
      {
        path: 'platform',
        element: <PlatformAdminPage />,
        label: 'Platform Admin',
        requireAuth: true,
        roles: ['platform_admin'],
        meta: {
          title: 'Platform Administration - Data Interoperability Hub',
        },
      },
      {
        path: 'users',
        element: <HomePage />,
        label: 'Users',
        requireAuth: true,
        roles: ['admin'],
        permissions: ['users.view'],
      },
    ],
  },

  // 404 - Must be last
  {
    path: '*',
    element: <NotFoundPage />,
    meta: {
      title: 'Not Found - Data Interoperability Hub',
    },
  },
]

/**
 * AppRoutes component
 * Renders all routes with guards and code splitting
 */
export const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        {routeConfig.map((route, index) => renderRoute(route, index))}
      </Routes>
    </BrowserRouter>
  )
}

// routeConfig is already exported above
