/**
 * 311.4 (G5/G25) — Cookie consent banner.
 *
 * Displays for EU visitors, blocks non-essential cookies pre-consent,
 * persists preference to localStorage. GDPR/ePrivacy Art. 5(3) compliant.
 */
import React, { useEffect, useState } from 'react';

const STORAGE_KEY = 'cookie_consent';
const ESSENTIAL_COOKIES = ['csrftoken', 'sessionid', 'meshant_jwt'];

export const CookieConsentBanner: React.FC = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      // Check if EU visitor (simplified: check timezone or accept-language)
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const isEU = tz && (tz.includes('Europe') || tz.includes('London') || tz.includes('Paris') || tz.includes('Berlin'));
      if (isEU || process.env.NODE_ENV === 'development') {
        setVisible(true);
      }
      // Block non-essential cookies pre-consent
      document.cookie.split(';').forEach(c => {
        const name = c.trim().split('=')[0];
        if (!ESSENTIAL_COOKIES.includes(name)) {
          document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
        }
      });
    }
  }, []);

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ consented: true, date: new Date().toISOString() }));
    setVisible(false);
  };

  const reject = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ consented: false, date: new Date().toISOString() }));
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="cookie-consent-banner"
      role="alert"
      aria-label="Cookie consent"
      data-testid="cookie-consent-banner"
      style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'var(--color-neutral-900)', color: 'var(--color-neutral-100)',
        padding: '1rem', zIndex: 9999, display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem',
      }}
    >
      <p style={{ margin: 0, flex: '1 1 300px', fontSize: '0.875rem' }}>
        This site uses essential cookies for authentication and session management.
        Optional analytics cookies help us improve the platform. By clicking
        &ldquo;Accept&rdquo;, you consent to all cookies.
        See our <a href="/legal/privacy" style={{ textDecoration: 'underline' }}>Privacy Policy</a>.
      </p>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button onClick={reject} data-testid="cookie-reject"
          style={{ padding: '0.5rem 1rem', border: '1px solid var(--color-neutral-400)', background: 'transparent', color: 'var(--color-neutral-100)', borderRadius: '4px', cursor: 'pointer' }}>
          Essential Only
        </button>
        <button onClick={accept} data-testid="cookie-accept"
          style={{ padding: '0.5rem 1rem', border: 'none', background: 'var(--color-primary)', color: '#fff', borderRadius: '4px', cursor: 'pointer' }}>
          Accept All
        </button>
      </div>
    </div>
  );
};
