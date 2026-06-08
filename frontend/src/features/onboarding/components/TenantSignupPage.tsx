/**
 * TenantSignupPage — self-service tenant onboarding (281.A.8.1).
 *
 * Backend API: POST /api/v1/admin/tenants/ (create_tenant in tenants/views.py:100)
 * Route: /signup (public, unauthenticated)
 */
import { useState, type FormEvent } from 'react';
import { apiClient } from '../../../shared/api/client';
import { Button } from '../../../shared/components/Button';
import { APP_NAME } from '../../../shared/constants/brand';
import './TenantSignupPage.css';

const PLANS = [
  { slug: 'free', name: 'Free', price: '$0/mo', limits: '10 assets, 1 GB storage' },
  { slug: 'pro', name: 'Pro', price: '$99/mo', limits: '500 assets, 50 GB storage' },
  { slug: 'enterprise', name: 'Enterprise', price: 'Custom', limits: 'Unlimited + SLA' },
];

interface FormData {
  companyName: string;
  tenantSlug: string;
  adminEmail: string;
  adminName: string;
  plan: string;
}

interface FormErrors {
  companyName?: string;
  tenantSlug?: string;
  adminEmail?: string;
  adminName?: string;
  plan?: string;
  server?: string;
}

export function TenantSignupPage() {
  const [step, setStep] = useState<'plan' | 'details' | 'submitting' | 'done'>('plan');
  const [form, setForm] = useState<FormData>({
    companyName: '',
    tenantSlug: '',
    adminEmail: '',
    adminName: '',
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
    if (!form.adminEmail.trim() || !/^[^\s@]+@[^\s@]+$/.test(form.adminEmail))
      e.adminEmail = 'Valid email is required';
    if (!form.adminName.trim()) e.adminName = 'Admin name is required';
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
      const resp = await client.post<{ id: string; tenant_id: string }>('admin/tenants/', {
        name: form.companyName.trim(),
        slug: form.tenantSlug.trim().toLowerCase(),
        admin_email: form.adminEmail.trim(),
        admin_name: form.adminName.trim(),
        plan_slug: form.plan,
      });
      setTenantId(resp.data?.id ?? resp.data?.tenant_id ?? null);
      setStep('done');
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message
        ?? err?.message
        ?? 'Provisioning failed. Please try again or contact support.';
      setErrors({ server: msg });
      setStep('details');
    }
  };

  return (
    <div className="tenant-signup-page" data-testid="tenant-signup-page">
      <div className="tenant-signup-card">
        <h1>Create your {APP_NAME} workspace</h1>

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
                <label htmlFor="adminName">Your name</label>
                <input
                  id="adminName"
                  type="text"
                  value={form.adminName}
                  onChange={e => updateField('adminName', e.target.value)}
                  required
                  aria-required="true"
                />
                {errors.adminName && <span className="field-error">{errors.adminName}</span>}
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
            <p>Creating your workspace…</p>
          </section>
        )}

        {step === 'done' && (
          <section className="tenant-signup-done">
            <h2>Workspace created!</h2>
            <p>
              Check <strong>{form.adminEmail}</strong> for your invitation email.
              Click the link to set your password and sign in.
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
