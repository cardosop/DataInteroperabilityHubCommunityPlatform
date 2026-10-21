/**
 * Password Reset Confirm Page (Visitor persona)
 *
 * Routes:
 * - /password-reset/confirm
 * - /auth/password-reset/confirm  (compat: backend email links)
 */
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { ApiError } from '../../../shared/types/api';
import { authService } from '../services/authService';
import { useAuthStore } from '../store/authStore';
import './AuthPage.css';

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  const apiErr = err as ApiError | undefined;
  if (apiErr?.error?.message) return apiErr.error.message;
  return 'Password reset failed';
}

export function PasswordResetConfirmPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuthStore();

  // ---------------------------------------------------------------------------
  // Phase 221.1.2 + 221.1.3 — Secure token extraction & URL cleanup
  //
  // Token sources (checked in priority order):
  //   1. URL fragment  (#token=…) — preferred: fragment is NEVER sent to the
  //      server, so it won't appear in access logs or Referer headers.
  //   2. Query string  (?token=…) — legacy / backward-compat with existing
  //      password-reset emails that may still use this format.
  //
  // After reading the token, we immediately strip it from the browser address
  // bar via history.replaceState so it cannot leak through:
  //   • the Referer header on outbound navigation,
  //   • browser history entries,
  //   • shoulder-surfing the address bar.
  // ---------------------------------------------------------------------------
  const tokenFromUrl = useMemo(() => {
    // 1. Try hash fragment first (never sent to server)
    const hash = location.hash;
    if (hash) {
      const fragmentParams = new URLSearchParams(hash.replace(/^#/, ''));
      const fromFragment = fragmentParams.get('token');
      if (fromFragment) return fromFragment;
    }
    // 2. Fallback to query string (legacy emails)
    const params = new URLSearchParams(location.search);
    return params.get('token') || '';
  }, [location.search, location.hash]);

  const [token, setToken] = useState(tokenFromUrl);
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Phase 221.1.2 — Clear token from URL immediately after reading it.
  useEffect(() => {
    if (tokenFromUrl) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [tokenFromUrl]);

  useEffect(() => {
    if (tokenFromUrl && !token) {
      setToken(tokenFromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenFromUrl]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!token) {
      setError('Missing reset token.');
      return;
    }

    setIsSubmitting(true);
    try {
      const resp = await authService.confirmPasswordReset({
        token,
        new_password: newPassword,
      });
      setSuccess(resp.message || 'Password reset successfully.');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page" role="main">
      <div className="auth-container">
        <h1>Set a new password</h1>

        {success && (
          <div className="success-message" role="status">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="token">Reset token</label>
            <input
              id="token"
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              readOnly={Boolean(tokenFromUrl)}
              autoComplete="off"
            />
          </div>

          <div className="form-group">
            <label htmlFor="new_password">New password</label>
            <input
              id="new_password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          <button type="submit" className="auth-button" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? 'Saving…' : 'Reset password'}
          </button>
        </form>

        <div className="auth-links">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}

