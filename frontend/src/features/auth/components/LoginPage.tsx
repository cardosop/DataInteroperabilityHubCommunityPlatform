/**
 * Login Page Component
 */

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { ApiError } from '../../../shared/types/api';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { authService } from '../services/authService';
import { useAuthStore } from '../store/authStore';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { APP_NAME } from '../../../shared/constants/brand';
import './AuthPage.css';

type LoginLocationState = {
  registered?: boolean;
  successMessage?: string;
  email?: string;
};

function isApiError(e: unknown): e is ApiError {
  return Boolean(e && typeof e === 'object' && 'error' in (e as object));
}

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const location = useLocation();
  const { login, isLoading } = useAuthStore();
  const navigate = useNavigate();
  const { isCapabilityAvailable, isLoading: capabilitiesLoading } = useCapabilities();

  const registrationEnabledEnv = (import.meta.env.VITE_AUTH_REGISTRATION_ENABLED as string | undefined) ?? 'auto';
  const registrationEnabled =
    registrationEnabledEnv === 'auto' ? isCapabilityAvailable('auth.register') : registrationEnabledEnv === 'true';
  const passwordResetEnabled = isCapabilityAvailable('auth.password-reset');

  const state = (location.state as LoginLocationState | null) ?? null;
  const registrationSuccess = Boolean(state?.registered);
  const successMessage =
    state?.successMessage ??
    (registrationSuccess ? 'Account created. You can now sign in.' : null);

  useEffect(() => {
    const stateEmail = state?.email;
    if (stateEmail && !email) {
      setEmail(stateEmail);
    }
    // We intentionally only prefill once (when email is empty).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setEmailNotVerified(false);
    setResendMessage(null);

    try {
      await login({ email, password });
      navigate('/');
    } catch (err) {
      if (isApiError(err) && err.error.code === 'EMAIL_NOT_VERIFIED') {
        setEmailNotVerified(true);
        return;
      }
      setError(normalizeError(err).error.message || 'Login failed');
    }
  };

  const handleResendVerification = async () => {
    if (!email.trim()) {
      setResendMessage('Enter your email address above, then try again.');
      return;
    }
    setResendBusy(true);
    setResendMessage(null);
    try {
      const r = await authService.resendVerificationEmail(email.trim());
      setResendMessage(r.message || 'If the account exists, a verification email has been sent.');
    } catch (re) {
      setResendMessage(normalizeError(re).error.message || 'Could not resend verification email.');
    } finally {
      setResendBusy(false);
    }
  };

  return (
    <div className="auth-page" role="main">
      <div className="auth-container">
        <h1>{APP_NAME}</h1>
        {successMessage && (
          <div className="success-message" role="status">
            {successMessage}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="auth-form"
        >
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              aria-required="true"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              aria-required="true"
            />
          </div>

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          {emailNotVerified && (
            <div className="error-message" role="alert">
              <p>Please verify your email before signing in.</p>
              <button
                type="button"
                className="auth-button"
                style={{ marginTop: '0.75rem' }}
                onClick={handleResendVerification}
                disabled={resendBusy}
                aria-busy={resendBusy}
              >
                {resendBusy ? 'Sending…' : 'Resend verification email'}
              </button>
              {resendMessage && (
                <p style={{ marginTop: '0.75rem', marginBottom: 0 }} role="status">
                  {resendMessage}
                </p>
              )}
            </div>
          )}

          <button
            type="submit"
            className="auth-button"
            disabled={isLoading}
            aria-busy={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="auth-links" aria-label="Authentication links">
          <Link to="/public">Public resources</Link>
          {!capabilitiesLoading && registrationEnabled && <Link to="/register">Create an account</Link>}
          {!capabilitiesLoading && passwordResetEnabled && <Link to="/password-reset">Forgot your password?</Link>}
        </div>
      </div>
    </div>
  );
}
