/**
 * Shown when a capability-gated route is unavailable in MVP deployments.
 */

import { Link, useLocation } from 'react-router-dom';
import './UnavailablePage.css';

export function ComingSoonPage() {
  const location = useLocation();
  const capability = location.state?.capability ?? 'This feature';

  return (
    <div className="unavailable-page" data-testid="coming-soon-page">
      <div className="unavailable-container">
        <h1>Coming soon</h1>
        <p>
          {capability} is not part of the current release. It will be enabled in a future update.
        </p>
        <Link to="/" className="back-link">
          Return to Home
        </Link>
      </div>
    </div>
  );
}
