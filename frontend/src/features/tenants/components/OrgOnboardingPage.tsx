/**
 * Organization Onboarding Page (Phase 16)
 * Self-service creation of non-personal org tenant with first user.
 * Route: /onboard-org
 * No auth required.
 */

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../auth/store/authStore';
import { tenantService } from '../services/tenantService';
import type { ApiError } from '../../../shared/types/api';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import '../../auth/components/AuthPage.css';
import './OrgOnboardingPage.css';

export function OrgOnboardingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();

  const [orgName, setOrgName] = useState('');
  const [slug, setSlug] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Auto-derive slug from org name; clear when org name cleared
  useEffect(() => {
    if (!orgName) {
      setSlug('');
    } else if (!slug) {
      setSlug(
        orgName
          .toLowerCase()
          .replace(/\s+/g, '-')
          .replace(/[^a-z0-9-_]/g, '')
      );
    }
  }, [orgName, slug]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      await tenantService.createOrgTenant({
        name: orgName,
        slug: slug || orgName.toLowerCase().replace(/\s+/g, '-'),
        plan_slug: 'free',
        first_user: {
          email,
          password,
          display_name: displayName || undefined,
        },
      });

      setSuccess('Organization created. Redirecting to sign in…');
      navigate('/login', {
        replace: true,
        state: {
          registered: true,
          email,
          successMessage: 'Organization created. Sign in with your admin account.',
        },
      });
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page org-onboarding-page" data-testid="org-onboarding-page">
      <div className="auth-container org-onboarding-container">
        <h1>Create organization</h1>
        <p className="org-onboarding-subtitle">
          Set up a new organization (tenant) with you as the admin. Free plan included.
        </p>

        {success && (
          <div className="success-message" role="status">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="org-name">Organization name</label>
            <input
              id="org-name"
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              required
              placeholder="My Company"
              autoComplete="organization"
              data-testid="org-onboarding-name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="org-slug">URL slug</label>
            <input
              id="org-slug"
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              required
              placeholder="my-company"
              pattern="[a-z0-9_-]+"
              title="Lowercase letters, numbers, hyphens, underscores only"
              data-testid="org-onboarding-slug"
            />
            <span className="form-hint">Lowercase, numbers, hyphens, underscores only</span>
          </div>

          <div className="form-group">
            <label htmlFor="admin-email">Admin email</label>
            <input
              id="admin-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              data-testid="org-onboarding-email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="admin-password">Admin password</label>
            <input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              minLength={8}
              data-testid="org-onboarding-password"
            />
          </div>

          <div className="form-group">
            <label htmlFor="admin-display-name">
              Display name <span className="optional">(optional)</span>
            </label>
            <input
              id="admin-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Admin User"
              autoComplete="name"
              data-testid="org-onboarding-display-name"
            />
          </div>

          {error && (
            <ErrorDisplay
              error={error}
              title="Organization creation failed"
              onRetry={() => setError(null)}
            />
          )}

          <button
            type="submit"
            className="auth-button"
            disabled={isSubmitting}
            aria-busy={isSubmitting}
            data-testid="org-onboarding-submit"
          >
            {isSubmitting ? 'Creating…' : 'Create organization'}
          </button>
        </form>

        <p className="org-onboarding-footer">
          Already have an account? <Link to="/login">Sign in</Link>
          {' · '}
          Need a personal account? <Link to="/register">Create account</Link>
        </p>
      </div>
    </div>
  );
}
