/**
 * Login Page Component
 */

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import './AuthPage.css';

type LoginLocationState = {
  registered?: boolean;
  successMessage?: string;
  email?: string;
};

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
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

    try {
      await login({ email, password });
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>Data Interoperability Hub</h1>
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
