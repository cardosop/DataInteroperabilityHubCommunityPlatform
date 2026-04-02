/**
 * Email verification landing (Phase 204).
 * Route: /verify-email?token=...
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { ApiError } from '../../../shared/types/api';
import { authService } from '../services/authService';
import { APP_NAME } from '../../../shared/constants/brand';
import './AuthPage.css';

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  const apiErr = err as ApiError | undefined;
  if (apiErr?.error?.message) return apiErr.error.message;
  return 'Verification failed';
}

export function VerifyEmailPage() {
  const location = useLocation();
  const tokenFromQuery = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('token') || '';
  }, [location.search]);

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!tokenFromQuery) {
      setStatus('error');
      setMessage('Missing verification token. Open the link from your email or request a new one from the login page.');
      return;
    }

    let cancelled = false;
    (async () => {
      setStatus('loading');
      setMessage(null);
      try {
        const resp = await authService.verifyEmail(tokenFromQuery);
        if (cancelled) return;
        setStatus('success');
        setMessage(resp.message || 'Your email has been verified. You can sign in.');
      } catch (err) {
        if (cancelled) return;
        setStatus('error');
        setMessage(extractErrorMessage(err));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tokenFromQuery]);

  return (
    <div className="auth-page" role="main">
      <div className="auth-container">
        <h1>{APP_NAME}</h1>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Email verification</h2>

        {status === 'loading' && (
          <p role="status" aria-busy="true">
            Verifying your email…
          </p>
        )}

        {status === 'success' && message && (
          <div className="success-message" role="status">
            {message}
          </div>
        )}

        {status === 'error' && message && (
          <div className="error-message" role="alert">
            {message}
          </div>
        )}

        <div className="auth-links" aria-label="Next steps">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
