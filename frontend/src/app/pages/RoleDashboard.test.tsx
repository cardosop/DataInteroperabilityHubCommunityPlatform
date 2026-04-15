/**
 * RoleDashboard Tests — Phase 224.2
 *
 * Asserts role-specific cards and the Actionable Items panel render based on
 * the authenticated user's roles. All data hooks are mocked so tests stay
 * hermetic (no real network, no QueryClientProvider wiring per test).
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../features/auth/store/authStore', () => ({
  useAuthStore: vi.fn(),
}));
vi.mock('../../features/assets/hooks/useAssets', () => ({
  useAssets: vi.fn(),
}));
vi.mock('../../features/governance/hooks/useGovernance', () => ({
  useAccessRequests: vi.fn(),
}));
vi.mock('../../features/marketplace/hooks/useOrders', () => ({
  useOrders: vi.fn(),
}));
vi.mock('../../features/marketplace/hooks/useEntitlements', () => ({
  useEntitlements: vi.fn(),
}));
vi.mock('../../features/audit/hooks/useAudit', () => ({
  useAuditEvents: vi.fn(),
}));

import { useAuthStore } from '../../features/auth/store/authStore';
import { useAssets } from '../../features/assets/hooks/useAssets';
import { useAccessRequests } from '../../features/governance/hooks/useGovernance';
import { useOrders } from '../../features/marketplace/hooks/useOrders';
import { useEntitlements } from '../../features/marketplace/hooks/useEntitlements';
import { useAuditEvents } from '../../features/audit/hooks/useAudit';
import { RoleDashboard } from './RoleDashboard';

const mockAuth = vi.mocked(useAuthStore);
const mockAssets = vi.mocked(useAssets);
const mockAR = vi.mocked(useAccessRequests);
const mockOrders = vi.mocked(useOrders);
const mockEnts = vi.mocked(useEntitlements);
const mockAudit = vi.mocked(useAuditEvents);

function pageResult<T>(count: number, results: T[] = []) {
  return {
    data: { count, next: null, previous: null, results },
    isLoading: false,
    error: null,
  };
}

function listResult<T>(results: T[]) {
  return { data: { count: results.length, next: null, previous: null, results }, isLoading: false, error: null };
}

function renderWithRoles(roles: string[]) {
  mockAuth.mockReturnValue({
    user: { id: 'u1', email: 'x@y.com', name: 'X', tenant_id: 't1', roles },
    isAuthenticated: true,
    isLoading: false,
  } as never);
  return render(
    <MemoryRouter>
      <RoleDashboard />
    </MemoryRouter>,
  );
}

describe('RoleDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAssets.mockReturnValue(pageResult(0) as never);
    mockAR.mockReturnValue(pageResult(0) as never);
    mockOrders.mockReturnValue(pageResult(0) as never);
    mockEnts.mockReturnValue(pageResult(0) as never);
    mockAudit.mockReturnValue(listResult([]) as never);
  });

  it('renders nothing visible when user has no matching roles', () => {
    renderWithRoles(['UNKNOWN_ROLE']);
    expect(screen.queryByTestId('role-dashboard')).not.toBeInTheDocument();
  });

  it('TENANT_ADMIN sees Pending Approvals card with count and link', () => {
    mockAR.mockReturnValue(pageResult(7) as never);
    renderWithRoles(['TENANT_ADMIN']);
    const card = screen.getByTestId('role-card-pending-approvals');
    expect(card).toHaveTextContent('7');
    expect(card.querySelector('a')).toHaveAttribute('href', '/governance');
  });

  it('DATA_PROVIDER sees My Draft Assets with CTA to activate', () => {
    mockAssets.mockReturnValue(pageResult(3) as never);
    renderWithRoles(['DATA_PROVIDER']);
    const card = screen.getByTestId('role-card-my-draft-assets');
    expect(card).toHaveTextContent('3');
    expect(card.querySelector('a')).toHaveAttribute('href', '/assets?status=DRAFT');
  });

  it('DATA_CONSUMER sees My Orders and My Entitlements summaries', () => {
    mockOrders.mockReturnValue(pageResult(4) as never);
    mockEnts.mockReturnValue(pageResult(9) as never);
    renderWithRoles(['DATA_CONSUMER']);
    expect(screen.getByTestId('role-card-my-orders')).toHaveTextContent('4');
    expect(screen.getByTestId('role-card-my-entitlements')).toHaveTextContent('9');
  });

  it('AUDITOR sees Recent Audit Events list and Compliance Summary', () => {
    mockAudit.mockReturnValue(
      listResult([
        {
          id: 'e1',
          tenant: 't1',
          tenant_name: 'T',
          actor_user: 'u1',
          actor_user_email: 'a@b.c',
          resource_type: 'ASSET',
          resource_id: 'a1',
          action: 'ASSET_CREATED',
          result: 'SUCCESS',
          details_json: {},
          timestamp: new Date().toISOString(),
        },
      ]) as never,
    );
    // total=10, compliant=7 → 70%; dispatch by filter keys
    mockAssets.mockImplementation((filters: Record<string, unknown> | undefined) => {
      if (filters?.compliance_status === 'COMPLIANT') return pageResult(7) as never;
      if (filters?.status === 'DRAFT') return pageResult(0) as never;
      return pageResult(10) as never;
    });
    renderWithRoles(['AUDITOR']);
    expect(screen.getByTestId('role-card-recent-audit')).toHaveTextContent('ASSET_CREATED');
    expect(screen.getByTestId('role-card-compliance-summary')).toHaveTextContent('70%');
  });

  it('renders Actionable Items for TENANT_ADMIN when approvals pending', () => {
    mockAR.mockReturnValue(pageResult(2) as never);
    renderWithRoles(['TENANT_ADMIN']);
    const panel = screen.getByTestId('actionable-items');
    expect(panel).toHaveTextContent(/2 pending access request/i);
  });

  it('renders Actionable Items for DATA_PROVIDER when DRAFT assets exist', () => {
    mockAssets.mockReturnValue(pageResult(5) as never);
    renderWithRoles(['DATA_PROVIDER']);
    const panel = screen.getByTestId('actionable-items');
    expect(panel).toHaveTextContent(/5 draft asset/i);
  });

  it('omits Actionable Items panel when nothing needs attention', () => {
    renderWithRoles(['DATA_CONSUMER']);
    expect(screen.queryByTestId('actionable-items')).not.toBeInTheDocument();
  });
});
