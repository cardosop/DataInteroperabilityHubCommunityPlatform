/**
 * Accept Invitation Page
 * Reads token from query; form with password; POST /auth/accept-invitation/; redirect on success.
 * Route: /accept-invitation?token=...
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { authService } from '../services/authService';
import './AcceptInvitationPage.css';

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const tokenFromQuery = searchParams.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!tokenFromQuery) {
      setError(new Error('Missing invitation token. Use the link from your invitation email.'));
    }
  }, [tokenFromQuery]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setError(null);
    if (password.length < 8) {
      setValidationError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setValidationError('Passwords do not match.');
      return;
    }
    if (!tokenFromQuery) {
      setValidationError('Invitation token is missing.');
      return;
    }
    setSubmitting(true);
    try {
      await authService.acceptInvitation({ token: tokenFromQuery, password });
      await authService.fetchAndStoreUser();
      navigate('/', { replace: true });
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="accept-invitation-page" data-testid="accept-invitation-page">
      <div className="accept-invitation-card" data-testid="accept-invitation-card">
        <h1>Accept Invitation</h1>
        <p className="accept-invitation-description">Set your password to activate your account.</p>

        {!tokenFromQuery ? (
          <div className="accept-invitation-missing-token">
            <p>No invitation token found. Please use the link from your invitation email.</p>
            <a href="/login">Go to login</a>
          </div>
        ) : (
          <>
            {error && (
              <ErrorDisplay
                error={error}
                title="Invitation failed"
                onRetry={() => setError(null)}
              />
            )}
            {validationError && (
              <p className="accept-invitation-validation-error" role="alert">
                {validationError}
              </p>
            )}
            <form onSubmit={handleSubmit} className="accept-invitation-form" data-testid="accept-invitation-form">
              <input type="hidden" name="token" value={tokenFromQuery} />
              <div className="form-group">
                <label htmlFor="password">
                  Password <span className="required">*</span>
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                />
              </div>
              <div className="form-group">
                <label htmlFor="confirmPassword">
                  Confirm password <span className="required">*</span>
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />
              </div>
              <div className="accept-invitation-actions">
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? 'Activating...' : 'Activate account'}
                </button>
                <a href="/login" className="link-cancel">
                  Cancel
                </a>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
