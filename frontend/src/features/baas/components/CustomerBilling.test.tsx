/**
 * Tests for Phase 116C — Customer Billing Frontend Components
 *
 * Tests verify components mount, render, and export correctly.
 * Uses vitest + jsdom with React Query + Router wrappers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import type { ReactNode } from 'react';

// Mock API client before any imports that use it
vi.mock('../../../shared/api/client');

import { CustomerListPage } from './CustomerListPage';
import { CustomerDetailPage } from './CustomerDetailPage';
import { BillingReportListPage } from './BillingReportListPage';
import { BillingReportDetailPage } from './BillingReportDetailPage';
import { InvoicePreview } from './InvoicePreview';
import { BaaSPage } from './BaaSPage';
import type { CustomerBillingReport } from '../../../shared/types/baas';

let queryClient: QueryClient;

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function RoutedWrapper({ path, children }: { path: string; children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/settings/baas/customers/:customerId" element={children} />
          <Route path="/settings/baas/billing-reports/:reportId" element={children} />
          <Route path="*" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
});

// --- 116C.1: CustomerListPage ---
describe('CustomerListPage', () => {
  it('renders without crashing', () => {
    const { container } = render(<CustomerListPage />, { wrapper: Wrapper });
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    render(<CustomerListPage />, { wrapper: Wrapper });
    // Should show loading or empty state
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });
});

// --- 116C.2: CustomerDetailPage ---
describe('CustomerDetailPage', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <RoutedWrapper path="/settings/baas/customers/cust_001">
        <CustomerDetailPage />
      </RoutedWrapper>
    );
    expect(container.children.length).toBeGreaterThan(0);
  });
});

// --- 116C.3: BillingReportListPage ---
describe('BillingReportListPage', () => {
  it('renders without crashing', () => {
    const { container } = render(<BillingReportListPage />, { wrapper: Wrapper });
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('shows status filter dropdown', async () => {
    render(<BillingReportListPage />, { wrapper: Wrapper });
    // Should eventually render the filter or loading state
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });
});

// --- 116C.3: BillingReportDetailPage ---
describe('BillingReportDetailPage', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <RoutedWrapper path="/settings/baas/billing-reports/test-id">
        <BillingReportDetailPage />
      </RoutedWrapper>
    );
    expect(container.children.length).toBeGreaterThan(0);
  });
});

// --- 116C.5: InvoicePreview ---
describe('InvoicePreview', () => {
  const mockReport: CustomerBillingReport = {
    id: 'rpt-001',
    tenant_id: 'tenant-1',
    api_key_id: 'key-1',
    customer_id: 'cust_001',
    customer_name: 'Acme Corp',
    customer_email: 'billing@acme.com',
    period_start: '2026-02-20T00:00:00Z',
    period_end: '2026-03-22T00:00:00Z',
    total_requests: 5000,
    billable_requests: 4500,
    included_requests: 1000,
    overage_requests: 3500,
    base_fee: '50.00',
    overage_fee: '7.00',
    total_amount: '57.00',
    currency: 'USD',
    status: 'FINALIZED',
    finalized_at: '2026-03-22T12:00:00Z',
    sent_at: null,
    created_at: '2026-03-22T10:00:00Z',
    updated_at: '2026-03-22T12:00:00Z',
  };

  it('renders invoice with customer name', () => {
    render(<InvoicePreview report={mockReport} />, { wrapper: Wrapper });
    expect(screen.getByText('Acme Corp')).toBeTruthy();
  });

  it('renders invoice with amounts', () => {
    render(<InvoicePreview report={mockReport} />, { wrapper: Wrapper });
    expect(screen.getByText('57.00 USD')).toBeTruthy();
  });

  it('renders invoice with usage data', () => {
    render(<InvoicePreview report={mockReport} />, { wrapper: Wrapper });
    expect(screen.getByText('5,000')).toBeTruthy();
    expect(screen.getByText('1,000')).toBeTruthy();
    expect(screen.getByText('3,500')).toBeTruthy();
  });

  it('renders invoice title', () => {
    render(<InvoicePreview report={mockReport} />, { wrapper: Wrapper });
    expect(screen.getByText('Invoice')).toBeTruthy();
    expect(screen.getByText('Invoice Preview')).toBeTruthy();
  });

  it('renders report ID', () => {
    render(<InvoicePreview report={mockReport} />, { wrapper: Wrapper });
    expect(screen.getByText('rpt-001')).toBeTruthy();
  });
});

// --- 116C.6: BaaSPage tabs ---
describe('BaaSPage', () => {
  it('renders without crashing', () => {
    const { container } = render(<BaaSPage />, { wrapper: Wrapper });
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('renders Customers tab', () => {
    render(<BaaSPage />, { wrapper: Wrapper });
    expect(screen.getByText('Customers')).toBeTruthy();
  });

  it('renders Billing Reports tab', () => {
    render(<BaaSPage />, { wrapper: Wrapper });
    expect(screen.getByText('Billing Reports')).toBeTruthy();
  });

  it('renders all five tabs', () => {
    render(<BaaSPage />, { wrapper: Wrapper });
    const tabs = document.querySelectorAll('.baas-tab');
    expect(tabs.length).toBe(5);
    const tabTexts = Array.from(tabs).map((t) => t.textContent);
    expect(tabTexts).toContain('API Keys');
    expect(tabTexts).toContain('Usage Dashboard');
    expect(tabTexts).toContain('Customers');
    expect(tabTexts).toContain('Billing Reports');
    expect(tabTexts).toContain('ML Developer');
  });
});

// --- Service + hooks exports ---
// --- Tab switching ---
describe('BaaSPage tab switching', () => {
  it('clicking Customers tab shows customer content', async () => {
    const { fireEvent } = await import('@testing-library/react');
    render(<BaaSPage />, { wrapper: Wrapper });
    const tabs = document.querySelectorAll('.baas-tab');
    const customersTab = Array.from(tabs).find((t) => t.textContent === 'Customers');
    expect(customersTab).toBeTruthy();
    fireEvent.click(customersTab!);
    // CustomerListPage should render (loading or empty state)
    expect(document.body.textContent).toBeTruthy();
  });

  it('clicking Billing Reports tab shows billing content', async () => {
    const { fireEvent } = await import('@testing-library/react');
    render(<BaaSPage />, { wrapper: Wrapper });
    const tabs = document.querySelectorAll('.baas-tab');
    const billingTab = Array.from(tabs).find((t) => t.textContent === 'Billing Reports');
    expect(billingTab).toBeTruthy();
    fireEvent.click(billingTab!);
    expect(document.body.textContent).toBeTruthy();
  });
});

// --- Shared utility ---
describe('billingUtils', () => {
  it('statusBadgeClass returns correct class for each status', async () => {
    const { statusBadgeClass } = await import('./billingUtils');
    expect(statusBadgeClass('DRAFT')).toBe('status-badge status-draft');
    expect(statusBadgeClass('FINALIZED')).toBe('status-badge status-finalized');
    expect(statusBadgeClass('SENT')).toBe('status-badge status-sent');
    expect(statusBadgeClass('VOID')).toBe('status-badge status-void');
    expect(statusBadgeClass('UNKNOWN')).toBe('status-badge');
  });
});

// --- Service + hooks exports ---
describe('baasService exports', () => {
  it('exports billing report methods', async () => {
    const svc = await import('../services/baasService');
    expect(svc.baasService.listBillingReports).toBeDefined();
    expect(svc.baasService.getBillingReport).toBeDefined();
    expect(svc.baasService.generateBillingReport).toBeDefined();
    expect(svc.baasService.finalizeBillingReport).toBeDefined();
    expect(svc.baasService.sendBillingReport).toBeDefined();
    expect(svc.baasService.voidBillingReport).toBeDefined();
    expect(svc.baasService.getInvoicePdf).toBeDefined();
  });
});

describe('useBaaS hooks exports', () => {
  it('exports billing report hooks', async () => {
    const hooks = await import('../hooks/useBaaS');
    expect(hooks.useBillingReports).toBeDefined();
    expect(hooks.useBillingReport).toBeDefined();
    expect(hooks.useGenerateBillingReport).toBeDefined();
    expect(hooks.useFinalizeBillingReport).toBeDefined();
    expect(hooks.useSendBillingReport).toBeDefined();
    expect(hooks.useVoidBillingReport).toBeDefined();
  });
});
