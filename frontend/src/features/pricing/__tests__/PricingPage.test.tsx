/**
 * close-test-coverage-gaps 3.2 — PricingPage suite (285.13.11.2).
 *
 * Real component tree (PricingCard + PricingComparison + Helmet + the
 * real authStore); only the API client is mocked (the
 * CpoCostOverviewPage pattern). Pins the documented page states
 * (loading/error/empty/loaded), the annual toggle, the logged-in CTA,
 * the SEO structured-data pipeline (Helmet context — jsdom cannot
 * inject head tags under react-helmet-async 3, see
 * SchemaOrgJsonLd.test.tsx), and the defensive contract that a
 * half-shaped response (ml plans without base_plans) renders instead
 * of crashing.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelmetProvider } from 'react-helmet-async';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlanPricing, PlanWithProfile, TierProfile } from '../../../shared/types/billing';
import { useAuthStore } from '../../auth/store/authStore';
import { PricingPage } from '../PricingPage';
import { buildStructuredData } from '../structuredData';

const mockGet = vi.fn();

vi.mock('../../../shared/api/client', () => ({
  apiClient: { getClient: () => ({ get: mockGet }) },
}));

function makePlan(overrides: Partial<PlanPricing> = {}): PlanPricing {
  return {
    id: 'p-free',
    name: 'Free',
    slug: 'free',
    tier: 'FREE',
    category: 'BASE',
    order: 0,
    price_amount_cents: 0,
    price_currency: 'USD',
    billing_interval: 'month',
    limits_json: { max_assets: 10, max_storage_gb: 1 },
    ...overrides,
  };
}

function makeProfile(overrides: Partial<TierProfile> = {}): TierProfile {
  return {
    headline: 'For individuals',
    description_markdown: 'desc',
    features_highlight: 'Up to 10 assets',
    feature_checkmarks: { api_access: true, sso: false },
    is_recommended: false,
    self_serve: true,
    sort_order: 0,
    ...overrides,
  };
}

function makeWrapper(overrides: Partial<PlanWithProfile> = {}): PlanWithProfile {
  return { plan: makePlan(), tier_profile: makeProfile(), ...overrides };
}

const LOADED_RESPONSE = {
  base_plans: [
    makeWrapper(),
    makeWrapper({
      plan: makePlan({
        id: 'p-pro',
        name: 'Pro',
        slug: 'pro',
        tier: 'PRO',
        order: 1,
        price_amount_cents: 9900,
      }),
      tier_profile: makeProfile({
        headline: 'For teams',
        is_recommended: true,
        feature_checkmarks: { api_access: true, sso: true },
      }),
    }),
  ],
  ml_plans: [
    makeWrapper({
      plan: makePlan({
        id: 'p-ml',
        name: 'ML Starter',
        slug: 'ml-starter',
        tier: 'FREE',
        category: 'ML_AI',
        price_amount_cents: 2500,
      }),
      tier_profile: makeProfile({ headline: 'ML add-on' }),
    }),
  ],
};

function renderPage() {
  return render(
    <HelmetProvider>
      <PricingPage />
    </HelmetProvider>,
  );
}

describe('PricingPage (close-test-coverage-gaps 3.2)', () => {
  beforeEach(() => {
    mockGet.mockReset();
    useAuthStore.setState({ isAuthenticated: false, user: null });
  });

  afterEach(() => {
    useAuthStore.setState({ isAuthenticated: false, user: null });
    // Helmet appends into document.head; clear between tests so the
    // JSON-LD assertions stay deterministic.
    document.head
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => el.remove());
  });

  it('shows the loading state until the pricing fetch settles', () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole('status')).toHaveTextContent('Loading plans');
  });

  it('shows the error state with the Error message and a Retry button', async () => {
    mockGet.mockRejectedValue(new Error('Billing service unreachable'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
    });
    expect(screen.getByRole('alert')).toHaveTextContent('Billing service unreachable');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeDefined();
  });

  it('shows the empty state when both plan lists are empty', async () => {
    mockGet.mockResolvedValue({ data: { base_plans: [], ml_plans: [] } });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/No plans available at this time/),
      ).toBeDefined();
    });
  });

  it('renders base and ML sections with cards, popular badge, and comparison', async () => {
    mockGet.mockResolvedValue({ data: LOADED_RESPONSE });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Platform Plans' })).toBeDefined();
    });

    // Card aria-labels carry the plan name + price (a11y 285.13.11.8).
    expect(screen.getByRole('region', { name: /Pro plan — / })).toBeDefined();
    expect(screen.getByLabelText('Most popular plan')).toBeDefined();

    // ML section.
    expect(screen.getByRole('heading', { name: 'ML / AI Add-ons' })).toBeDefined();
    expect(screen.getByRole('region', { name: /ML Starter plan — / })).toBeDefined();

    // Feature comparison matrix (role=grid) renders with the union of
    // checkmark keys.
    const grid = screen.getByRole('grid', { name: 'Feature comparison' });
    expect(within(grid).getByRole('columnheader', { name: 'Free' })).toBeDefined();
    expect(within(grid).getByText('api access')).toBeDefined();
    expect(within(grid).getByText('sso')).toBeDefined();
  });

  it('renders no comparison grid when no tier profile carries checkmarks', async () => {
    const bare = {
      base_plans: [makeWrapper({ tier_profile: null })],
      ml_plans: [],
    };
    mockGet.mockResolvedValue({ data: bare });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Platform Plans' })).toBeDefined();
    });
    expect(screen.queryByRole('grid', { name: 'Feature comparison' })).toBeNull();
  });

  it('toggles annual pricing: price period and aria-checked flip', async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue({
      data: {
        base_plans: [
          makeWrapper({
            plan: makePlan({ price_amount_cents: 1000 }),
            tier_profile: makeProfile({ feature_checkmarks: {} }),
          }),
        ],
        ml_plans: [],
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('region', { name: /Free plan/ })).toBeDefined();
    });

    const monthly = screen.getByRole('radio', { name: /Monthly/ });
    const annual = screen.getByRole('radio', { name: /Annual/ });
    expect(monthly).toHaveAttribute('aria-checked', 'true');

    await user.click(annual);
    expect(annual).toHaveAttribute('aria-checked', 'true');
    // computeAnnual: 1000 * 12 * 0.85 = 10200 → $102/yr.
    const card = screen.getByRole('region', { name: /Free plan/ });
    expect(within(card).getByText('/yr')).toBeDefined();
    expect(within(card).getByText('$102')).toBeDefined();
  });

  it('shows the upgrade CTA for a logged-in user on a self-serve plan', async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue({ data: LOADED_RESPONSE });
    useAuthStore.setState({
      isAuthenticated: true,
      user: { id: 'u-1', email: 'a@b.c', roles: [] } as unknown as import('../../../shared/types/auth').User,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('region', { name: /Pro plan/ })).toBeDefined();
    });

    const proCard = screen.getByRole('region', { name: /Pro plan/ });
    expect(within(proCard).getByRole('button', { name: 'Select Pro plan' })).toBeDefined();

    // Real behavior: CTA navigates to /register with the plan slug.
    const locationRef: { href: string } = { href: '' };
    Object.defineProperty(window, 'location', {
      value: locationRef,
      writable: true,
    });
    await user.click(within(proCard).getByRole('button', { name: 'Select Pro plan' }));
    expect(locationRef.href).toBe('/register?plan=pro');
  });

  it('renders no CTA for a logged-out visitor', async () => {
    mockGet.mockResolvedValue({ data: LOADED_RESPONSE });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('region', { name: /Pro plan/ })).toBeDefined();
    });
    expect(screen.queryByRole('button', { name: 'Select Pro plan' })).toBeNull();
  });

  it('renders the SEO meta surface (title, description, canonical)', async () => {
    mockGet.mockResolvedValue({ data: LOADED_RESPONSE });
    renderPage();
    // React 19 hoists Helmet's title/meta/link into document.head natively.
    await waitFor(() => {
      expect(document.title).toBe('Pricing — Meshant');
    });
    expect(
      document.head.querySelector('meta[name="description"]')?.getAttribute('content'),
    ).toContain('Meshant pricing plans');
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://meshant.com/pricing',
    );
  });

  it('builds SoftwareApplication JSON-LD with the pinned offers math', () => {
    // Pure mapper pin — react-helmet-async 3 + React 19 + jsdom never
    // lands <script> children in document.head (SchemaOrgJsonLd.test.tsx
    // precedent); the real-browser emission is E2E-pinned
    // (frontend/e2e/journeys/seo/schemaorg-public.spec.ts).
    const structured = buildStructuredData(LOADED_RESPONSE);
    expect(structured).not.toBeNull();
    expect(structured!['@type']).toBe('SoftwareApplication');
    expect(structured!.name).toBe('Meshant');
    const offers = structured!.offers as {
      priceCurrency: string;
      lowPrice: string;
      highPrice: string;
    };
    expect(offers.priceCurrency).toBe('USD');
    // Paid base plans: Pro 9900 + ML 2500 is in ml_plans (excluded) —
    // lowPrice = 99 (9900/100), highPrice = 99 (only one paid base plan).
    expect(offers.lowPrice).toBe('99');
    expect(offers.highPrice).toBe('99');

    // No paid base plans → lowPrice '0'.
    const freeOnly = buildStructuredData({
      base_plans: [makeWrapper()],
      ml_plans: [],
    });
    expect((freeOnly!.offers as { lowPrice: string }).lowPrice).toBe('0');

    // Null / empty → null (no JSON-LD emitted).
    expect(buildStructuredData(null)).toBeNull();
    expect(buildStructuredData({ base_plans: [], ml_plans: [] })).toBeNull();
  });

  it('renders ml plans without crashing when base_plans is absent', async () => {
    // Defensive contract: the empty-state logic tolerates a missing
    // list, so the render path must too (the wire type says required,
    // but a partial response must degrade to a rendered page, never a
    // TypeError).
    const partial = {
      ml_plans: [
        makeWrapper({
          plan: makePlan({ id: 'p-ml2', name: 'ML Pro', slug: 'ml-pro', category: 'ML_AI' }),
        }),
      ],
    };
    mockGet.mockResolvedValue({ data: partial });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ML / AI Add-ons' })).toBeDefined();
    });
    expect(screen.getByRole('region', { name: /ML Pro plan/ })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Platform Plans' })).toBeNull();
  });
});
