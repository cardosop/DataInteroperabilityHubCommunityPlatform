/**
 * Public Resources Page (Visitor persona)
 * Route: /public
 *
 * This page is intentionally minimal and safe to expose without auth.
 */
import { Link, Navigate } from 'react-router-dom';
import './AuthPage.css';

export function PublicResourcesPage() {
  const enabledEnv = (import.meta.env.VITE_PUBLIC_RESOURCES_ENABLED as string | undefined) ?? 'true';
  if (enabledEnv !== 'true') {
    return <Navigate to="/login" replace />;
  }

  const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8001/api/v1';
  const openApiUrl = `${apiBase.replace(/\/$/, '')}/openapi.json`;
  const healthUrl = `${apiBase.replace(/\/api\/v1\/?$/, '')}/health`;

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>Public Resources</h1>
        <p style={{ marginBottom: 'var(--spacing-md)', color: 'var(--color-neutral-700)' }}>
          You can access these resources without signing in (depending on deployment configuration).
        </p>

        <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--color-neutral-700)' }}>
          <li>
            <a href={openApiUrl} target="_blank" rel="noreferrer">
              OpenAPI (JSON)
            </a>
          </li>
          <li>
            <a href={healthUrl} target="_blank" rel="noreferrer">
              Health check
            </a>
          </li>
        </ul>

        <div className="auth-links">
          <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

