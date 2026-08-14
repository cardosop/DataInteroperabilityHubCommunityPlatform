/**
 * 285.13.11.7 — Billing TypeScript interfaces.
 *
 * Covers plan pricing, tier profiles, usage limits, invoices,
 * and upgrade previews consumed by the pricing page, plan settings,
 * billing history, and usage banner components.
 */

// ── Plan Pricing ──────────────────────────────────────────────────────────

export interface PlanPricing {
  id: string;
  name: string;
  slug: string;
  tier: 'FREE' | 'PRO' | 'ENTERPRISE';
  category: 'BASE' | 'ML_AI';
  order: number;
  price_amount_cents: number;
  price_currency: string;
  billing_interval: 'month' | 'year';
  limits_json: Record<string, number | null>;
}

export interface TierProfile {
  headline: string;
  description_markdown: string;
  features_highlight: string;
  feature_checkmarks: Record<string, boolean>;
  is_recommended: boolean;
  self_serve: boolean;
  sort_order: number;
}

export interface PlanWithProfile {
  plan: PlanPricing;
  tier_profile: TierProfile | null;
}

export interface PublicPricingResponse {
  base_plans: PlanWithProfile[];
  ml_plans: PlanWithProfile[];
}

// ── Usage ──────────────────────────────────────────────────────────────────

export type UsageThreshold = 'ok' | 'warning' | 'critical' | 'exceeded';

export interface UsageLimit {
  limit_key: string;
  usage: number;
  limit: number | null; // null = unlimited
  percentage: number | null;
  status: UsageThreshold;
}

export interface UsageStatus {
  tenant_id: string;
  plan_slug: string;
  plan_tier: string;
  overall_status: UsageThreshold;
  limits: UsageLimit[];
  upgrade_recommendation: UpgradeRecommendation | null;
}

export interface UpgradeRecommendation {
  plan_slug: string;
  plan_name: string;
  reason: string;
}

// ── Invoices ───────────────────────────────────────────────────────────────

export interface Invoice {
  id: string;
  subscription_id?: string;
  amount_due_cents: number;
  amount_paid_cents: number;
  currency: string;
  status: 'draft' | 'open' | 'paid' | 'uncollectible' | 'void';
  period_start: string;
  period_end: string;
  due_date?: string;
  paid_at?: string;
  invoice_pdf_url?: string;
  hosted_invoice_url?: string;
  category?: 'BASE' | 'ML_AI';
}

// ── Upgrade / Downgrade ────────────────────────────────────────────────────

export interface UpgradePreview {
  current_plan: PlanPricing;
  target_plan: PlanPricing & { tier_profile?: TierProfile };
  annual_savings_cents: number;
  proration_note: string;
}

export interface PlanChangeRequest {
  plan_slug: string;
}

export interface PlanChangeResponse {
  message: string;
  subscription_id: string;
  plan_slug: string;
}
