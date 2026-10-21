/**
 * Skip Link Component
 * Provides keyboard-accessible skip navigation for screen readers
 */

import './SkipLink.css';

export function SkipLink() {
  return (
    <a href="#main-content" className="skip-link">
      Skip to main content
    </a>
  );
}
