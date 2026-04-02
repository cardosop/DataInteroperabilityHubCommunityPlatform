/**
 * Landing Page
 * Public landing shown at / when user is not authenticated.
 * Hero, value proposition, and links to login/signup.
 */

import { Link } from 'react-router-dom';
import { useCapabilities } from '../../shared/hooks/useCapabilities';
import { APP_NAME } from '../../shared/constants/brand';
import './LandingPage.css';

export function LandingPage() {
  const { isCapabilityAvailable, isLoading: capabilitiesLoading } = useCapabilities();
  const registrationEnabledEnv = (import.meta.env.VITE_AUTH_REGISTRATION_ENABLED as string | undefined) ?? 'auto';
  const registrationEnabled =
    registrationEnabledEnv === 'auto' ? isCapabilityAvailable('auth.register') : registrationEnabledEnv === 'true';

  return (
    <div className="landing-page" data-testid="landing-page" role="main">
      <header className="landing-hero">
        <h1 className="landing-hero-title">{APP_NAME}</h1>
        <p className="landing-hero-subtitle">
          Connect, govern, and share data across your organization with a single platform for assets, contracts, and
          compliance.
        </p>
      </header>

      <section className="landing-value" aria-label="Value proposition">
        <h2 className="visually-hidden">Why use the hub</h2>
        <ul className="landing-value-list">
          <li>Publish and discover data assets and datasets</li>
          <li>Manage contracts and access with governance</li>
          <li>Integrate with marketplaces and external systems</li>
        </ul>
      </section>

      <section className="landing-actions" aria-label="Sign in or sign up">
        <Link to="/login" className="landing-button landing-button-primary" data-testid="landing-login-link">
          Sign in
        </Link>
        {!capabilitiesLoading && registrationEnabled && (
          <Link to="/register" className="landing-button landing-button-secondary" data-testid="landing-register-link">
            Create an account
          </Link>
        )}
        {/* Organization creation moved to Platform Admin panel (/admin → Tenants tab) */}
        <Link to="/public" className="landing-link">
          Public resources
        </Link>
      </section>
    </div>
  );
}
