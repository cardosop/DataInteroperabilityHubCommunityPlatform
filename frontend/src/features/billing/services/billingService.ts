/**
 * Billing Service
 * API client for subscription and billing operations
 */

import { apiClient } from '../../../shared/api/client';

const BILLING_SUBSCRIPTION_PATH = 'billing/subscription';
const BILLING_PLANS_PATH = 'billing/plans';
const BILLING_INVOICES_PATH = 'billing/invoices';

export interface Subscription {
  id: string;
  tenant: string;
  plan: string;
  plan_name: string;
  plan_slug: string;
  plan_tier: string;
  limits: Record<string, number | null>;
  status: string;
  // Stripe IDs only present for TENANT_ADMIN / PLATFORM_ADMIN (Phase 113.F.2)
  stripe_subscription_id?: string | null;
  stripe_customer_id?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  trial_end?: string | null;
  canceled_at?: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantPlan {
  id: string;
  name: string;
  slug: string;
  tier: string;
  order: number;
  limits_json: Record<string, number | null>;
  is_active: boolean;
  price_amount_cents: number;
  price_currency: string;
  billing_interval: string;
}

export interface Invoice {
  id: string;
  tenant: string;
  subscription?: string | null;
  subscription_status?: string | null;
  // stripe_invoice_id only present for TENANT_ADMIN / PLATFORM_ADMIN (Phase 113.F.2)
  stripe_invoice_id?: string;
  amount_due: string;
  amount_paid: string;
  currency: string;
  status: string;
  invoice_pdf_url?: string | null;
  hosted_invoice_url?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  due_date?: string | null;
  paid_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Known error codes returned by the billing API */
export type BillingErrorCode =
  | 'plan_limit_exceeded'
  | 'tenant_suspended'
  | 'subscription_inactive'
  | 'PLAN_HAS_ACTIVE_SUBSCRIPTIONS'
  | 'STRIPE_ERROR';

export interface BillingApiError {
  error?: string;
  code?: BillingErrorCode;
  details?: Record<string, unknown>;
}

export const billingService = {
  /**
   * Get current subscription for the tenant
   */
  async getCurrentSubscription(): Promise<Subscription> {
    const response = await apiClient
      .getClient()
      .get<Subscription>(`${BILLING_SUBSCRIPTION_PATH}/current/`);
    return response.data;
  },

  /**
   * Change subscription plan (requires TENANT_ADMIN or PLATFORM_ADMIN)
   */
  async changePlan(planSlug: string): Promise<Subscription> {
    const response = await apiClient
      .getClient()
      .post<Subscription>(`${BILLING_SUBSCRIPTION_PATH}/current/change-plan/`, {
        plan_slug: planSlug,
      });
    return response.data;
  },

  /**
   * List available plans for subscription change
   */
  async getPlans(): Promise<TenantPlan[]> {
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<TenantPlan>>(`${BILLING_PLANS_PATH}/`);
    return response.data.results;
  },

  /**
   * List invoices for the tenant
   */
  async getInvoices(): Promise<Invoice[]> {
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<Invoice>>(`${BILLING_INVOICES_PATH}/`);
    return response.data.results;
  },

  /**
   * Get invoice download URL (redirects via backend, not direct Stripe URL)
   */
  getInvoiceDownloadUrl(invoiceId: string): string {
    return `/api/v1/${BILLING_INVOICES_PATH}/${invoiceId}/download/`;
  },

  /**
   * Get ML add-on subscription for the tenant (if any)
   */
  async getMLSubscription(): Promise<Subscription | null> {
    try {
      const response = await apiClient
        .getClient()
        .get<Subscription>('billing/ml-subscription/current/');
      return response.data;
    } catch {
      return null;
    }
  },
};
