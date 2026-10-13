/**
 * TenantSignupPage — PLATFORM_ADMIN tenant provisioning
 * (close-test-coverage-gaps 3.0).
 *
 * Checkpoint 3.0 verified the backend org-creation permission contract:
 * POST /api/v1/admin/tenants/ is `IsAuthenticated + IsPlatformAdmin` and
 * accepts EXACTLY `{slug, display_name, jurisdiction, admin_email,
 * plan_slug?}` (`AdminTenantCreateSerializer`). The route is
 * PLATFORM_ADMIN-gated in routes.tsx (ProtectedRoute); this page posts the
 * admin wire shape and renders the invitation-email outcome — the platform
 * provisions the tenant and invites its first TENANT_ADMIN (7-day
 * invitation token), it does not self-serve an active user.
 *
 * Backend API: POST /api/v1/admin/tenants/ (admin_tenant_create.py)
 * Route: /signup (PLATFORM_ADMIN — ProtectedRoute, not public)
 */
import { useState, type FormEvent } from 'react';
import { apiClient } from '../../../shared/api/client';
import { Button } from '../../../shared/components/Button';
import { APP_NAME } from '../../../shared/constants/brand';
import './TenantSignupPage.css';

// Mirrors `hub.apps.tenants.validators.VALID_COMPLIANCE_REGIMES` — the
// registry the backend validates `jurisdiction` against. There is no
// public listing endpoint, so the mirror is pinned by
// TenantSignupPage.test.tsx (32 entries + sentinels); a backend regime
// change must sync here (close-test-coverage-gaps 3.0).
const COMPLIANCE_REGIMES = [
  // EU / UK
  'GDPR',
  'GDPR_SCHREMS_II',
  'UK_GDPR',
  // Americas
  'LGPD',
  'CCPA',
  'COPPA',
  'FERPA',
  'GLBA',
  'HIPAA',
  'SOX',
  'PIPEDA',
  // US state privacy laws
  'CPA',
  'CTDPA',
  'ICDPA',
  'MCDPA',
  'MHMDA',
  'MTCDPA',
  'NHPA',
  'NJDPA',
  'OCPA',
  'TDPSA',
  'TIPA',
  'UCPA',
  'VCDPA',
  // APAC
  'APPI_JP',
  'DPDP_IN',
  'PDPA_SG',
  'PIPA_KR',
  'PIPL_CN',
  'PRIVACY_ACT_AU',
  // Africa
  'POPIA_ZA',
  // Industry
  'PCI_DSS',
];

// Slugs mirror the seeded TenantPlan rows (seed_default_plans:
// free / pro / enterprise). plan_slug is optional server-side and
// defaults to "free".
const PLANS = [
  { slug: 'free', name: 'Free', price: '$0/mo', limits: '10 assets, 1 GB storage' },
  { slug: 'pro', name: 'Pro', price: '$99/mo', limits: '500 assets, 50 GB storage' },
  { slug: 'enterprise', name: 'Enterprise', price: 'Custom', limits: 'Unlimited + SLA' },
];

interface FormData {
  companyName: string;
  tenantSlug: string;
  jurisdiction: string;
  adminEmail: string;
  plan: string;
}

interface FormErrors {
  companyName?: string;
  tenantSlug?: string;
  jurisdiction?: string;
  adminEmail?: string;
  server?: string;
}

/** DRF 400 field errors land keyed by serializer field name — map them
 * onto the operator-facing labels for the form fields. */
const FIELD_LABELS: Record<string, string> = {
  display_name: 'Company name',
  slug: 'Workspace URL',
  jurisdiction: 'Jurisdiction',
  admin_email: 'Work email',
  plan_slug: 'Plan',
};

export function TenantSignupPage() {
  const [step, setStep] = useState<'plan' | 'details' | 'submitting' | 'done'>('plan');
  const [form, setForm] = useState<FormData>({
    companyName: '',
    tenantSlug: '',
    jurisdiction: '',
    adminEmail: '',
    plan: 'pro',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [tenantId, setTenantId] = useState<string | null>(null);

  const updateField = (field: keyof FormData, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  const validate = (): boolean => {
    const e: FormErrors = {};
    if (!form.companyName.trim()) e.companyName = 'Company name is required';
    if (!form.tenantSlug.trim() || !/^[a-z0-9-]+$/.test(form.tenantSlug))
      e.tenantSlug = 'Slug must be lowercase letters, numbers, and hyphens';
    if (!form.jurisdiction) e.jurisdiction = 'Jurisdiction is required';
    if (!form.adminEmail.trim() || !/^[^\s@]+@[^\s@]+$/.test(form.adminEmail))
      e.adminEmail = 'Valid email is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setStep('submitting');
    setErrors({});

    try {
      const client = apiClient.getClient();
      const resp = await client.post<{
        tenant?: { id?: string };
      }>('admin/tenants/', {
        slug: form.tenantSlug.trim().toLowerCase(),
        display_name: form.companyName.trim(),
        jurisdiction: form.jurisdiction,
        admin_email: form.adminEmail.trim(),
        plan_slug: form.plan,
      });
      setTenantId(resp.data?.tenant?.id ?? null);
      setStep('done');
    } catch (err) {
      setErrors({ server: serverErrorMessage(err) });
      setStep('details');
    }
  };

  return (
    <div className="tenant-signup-page" data-testid="tenant-signup-page">
      <div className="tenant-signup-card">
        <h1>Create a {APP_NAME} workspace</h1>
        <p className="tenant-signup-subtitle">
          Platform administrators provision workspaces here; the tenant's first
          administrator receives a 7-day invitation email to set their password.
        </p>

        {step === 'plan' && (
          <section className="tenant-signup-plans">
            <p className="tenant-signup-subtitle">Choose a plan to get started.</p>
            <div className="plan-grid">
              {PLANS.map(p => (
                <button
                  key={p.slug}
                  type="button"
                  className={`plan-card ${form.plan === p.slug ? 'plan-card--selected' : ''}`}
                  onClick={() => setForm(prev => ({ ...prev, plan: p.slug }))}
                  data-testid={`plan-${p.slug}`}
                  data-plan-slug={p.slug}
                >
                  <span className="plan-name">{p.name}</span>
                  <span className="plan-price">{p.price}</span>
                  <span className="plan-limits">{p.limits}</span>
                </button>
              ))}
            </div>
            <Button
              variant="primary"
              onClick={() => setStep('details')}
              data-testid="plan-continue"
            >
              Continue with {PLANS.find(p => p.slug === form.plan)?.name ?? 'Pro'}
            </Button>
          </section>
        )}

        {step === 'details' && (
          <section className="tenant-signup-form">
            <p className="tenant-signup-subtitle">
              Plan: <strong>{PLANS.find(p => p.slug === form.plan)?.name}</strong>
              {' · '}
              <button type="button" className="link-button" onClick={() => setStep('plan')}>
                Change
              </button>
            </p>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="companyName">Company name</label>
                <input
                  id="companyName"
                  type="text"
                  value={form.companyName}
                  onChange={e => updateField('companyName', e.target.value)}
                  required
                  aria-required="true"
                />
                {errors.companyName && <span className="field-error">{errors.companyName}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="tenantSlug">Workspace URL</label>
                <div className="slug-input">
                  <span className="slug-prefix">meshant.com/</span>
                  <input
                    id="tenantSlug"
                    type="text"
                    value={form.tenantSlug}
                    onChange={e => updateField('tenantSlug', e.target.value.toLowerCase())}
                    required
                    aria-required="true"
                    placeholder="your-company"
                  />
                </div>
                {errors.tenantSlug && <span className="field-error">{errors.tenantSlug}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="jurisdiction">Jurisdiction</label>
                <select
                  id="jurisdiction"
                  value={form.jurisdiction}
                  onChange={e => updateField('jurisdiction', e.target.value)}
                  required
                  aria-required="true"
                >
                  {COMPLIANCE_REGIMES.map(regime => (
                    <option key={regime} value={regime}>
                      {regime}
                    </option>
                  ))}
                </select>
                {errors.jurisdiction && <span className="field-error">{errors.jurisdiction}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="adminEmail">Work email</label>
                <input
                  id="adminEmail"
                  type="email"
                  value={form.adminEmail}
                  onChange={e => updateField('adminEmail', e.target.value)}
                  required
                  aria-required="true"
                />
                {errors.adminEmail && <span className="field-error">{errors.adminEmail}</span>}
              </div>

              {errors.server && (
                <div className="server-error" role="alert">{errors.server}</div>
              )}

              <Button type="submit" variant="primary" data-testid="signup-submit">
                Create workspace
              </Button>
            </form>
          </section>
        )}

        {step === 'submitting' && (
          <section className="tenant-signup-submitting">
            <p>Creating the workspace…</p>
          </section>
        )}

        {step === 'done' && (
          <section className="tenant-signup-done" data-testid="tenant-signup-done">
            <h2>Workspace created!</h2>
            <p>
              The invitation email is on its way to <strong>{form.adminEmail}</strong>.
              The link sets their password and signs them in as the workspace's
              first administrator.
            </p>
            {tenantId && <p className="tenant-id">Workspace ID: {tenantId}</p>}
            <p>
              <a href="mailto:support@meshant.com">Need help? Contact support.</a>
            </p>
          </section>
        )}
      </div>
    </div>
  );
}

/** The axios-shaped error envelope the API client rejects with. */
interface ApiErrorShape {
  response?: {
    status?: number;
    data?: unknown;
  };
  message?: unknown;
}

/** Translate the REAL wire shapes this endpoint can return into
 * operator-facing copy (verified against hub/apps/api/exceptions.py):
 *
 * - 422: ``{code, detail}`` — returned directly by AdminTenantCreateView
 *   (TENANT_SLUG_DUPLICATE / ADMIN_EMAIL_DUPLICATE); view-built
 *   responses do NOT pass through the exception handler.
 * - 400: the platform exception-handler envelope —
 *   ``{error: {code: "VALIDATION_ERROR", message, ...}, <field>:
 *   "<first error string>", ...}`` (field errors are preserved at the
 *   TOP level as plain strings, not arrays).
 * - 401/403: the same envelope with ``error.code`` AUTH_* — there is
 *   NO raw-DRF ``{detail}`` key on the wire.
 */
function serverErrorMessage(err: unknown): string {
  const response = (err as ApiErrorShape | null | undefined)?.response;
  const data = response?.data;

  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const record = data as Record<string, unknown>;
    const envelope =
      typeof record.error === 'object' && record.error !== null
        ? (record.error as Record<string, unknown>)
        : null;

    // 422 business-code shape first — it is the most actionable.
    if (record.code === 'TENANT_SLUG_DUPLICATE') {
      return 'That workspace URL is already taken. Choose another.';
    }
    if (record.code === 'ADMIN_EMAIL_DUPLICATE') {
      return 'That email is already registered. Invite the person from the Users admin instead.';
    }

    // The permission layer (envelope carries the status in both places).
    if (response?.status === 403 || envelope?.http_status === 403) {
      return 'Only platform administrators can create workspaces.';
    }
    if (response?.status === 401 || envelope?.http_status === 401) {
      return 'You must be signed in as a platform administrator.';
    }

    // 400 field errors preserved at the top level by the exception
    // handler: map the first known serializer field to its label.
    for (const [field, label] of Object.entries(FIELD_LABELS)) {
      const value = record[field];
      if (typeof value === 'string' && value) {
        return `${label}: ${value}`;
      }
    }
    // Fallback for unknown fields / non_field_errors.
    for (const [key, value] of Object.entries(record)) {
      if (key === 'error') continue;
      if (typeof value === 'string' && value) {
        return value;
      }
    }

    if (envelope && typeof envelope.message === 'string' && envelope.message) {
      return envelope.message;
    }
  }

  const message = (err as ApiErrorShape | null | undefined)?.message;
  if (typeof message === 'string' && message) {
    return message;
  }
  return 'Provisioning failed. Please try again or contact support.';
}
