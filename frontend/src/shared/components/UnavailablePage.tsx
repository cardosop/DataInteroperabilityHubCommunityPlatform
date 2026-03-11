/**
 * Unavailable Page Component
 * Shown when a capability is not available
 */

import { useLocation, Link } from 'react-router-dom';
import './UnavailablePage.css';

interface UnavailablePageProps {
  title?: string;
  message?: string;
}

export function UnavailablePage({ title, message }: UnavailablePageProps = {}) {
  const location = useLocation();
  const capability = location.state?.capability ?? title ?? 'This feature';
  const description = message ?? `${capability} is not available in your current environment or requires additional configuration.`;

  return (
    <div className="unavailable-page" data-testid="unavailable-page">
      <div className="unavailable-container">
        <h1>{title ?? 'Feature Unavailable'}</h1>
        <p>
          {description}
        </p>
        <p className="unavailable-details">
          This feature may be:
        </p>
        <ul>
          <li>Not enabled in your deployment</li>
          <li>Requiring backend dependencies that are not yet implemented</li>
          <li>Available only in specific environments</li>
        </ul>
        <Link to="/" className="back-link">
          Return to Home
        </Link>
      </div>
    </div>
  );
}
