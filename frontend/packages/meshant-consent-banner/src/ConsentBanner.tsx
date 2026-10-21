/**
 * IAB TCF v2.2–compatible shell: surfaces CMP actions and optional tcString.
 * Wire your registered CMP ID / GVL version via props; this component stays
 * presentational so host apps control persistence and API calls.
 */
import { useCallback, type CSSProperties } from 'react';

export type ConsentBannerProps = {
  policyUrl?: string;
  vendorListVersion?: number;
  /** When set, exposed to analytics adapters as the resolved TC string. */
  tcString?: string;
  onAcceptAll: () => void;
  onRejectAll?: () => void;
  onManagePreferences?: () => void;
};

declare global {
  interface Window {
    __tcfapi?: (command: string, version: number, callback: (tcData: unknown, success: boolean) => void) => void;
  }
}

export function ConsentBanner({
  policyUrl = '/privacy',
  vendorListVersion = 77,
  tcString,
  onAcceptAll,
  onRejectAll,
  onManagePreferences,
}: ConsentBannerProps) {
  const pushDataLayer = useCallback(
    (event: string, detail: Record<string, unknown>) => {
      const w = window as unknown as { dataLayer?: unknown[] };
      w.dataLayer = w.dataLayer || [];
      w.dataLayer.push({
        event,
        tcf: { vendorListVersion, tcString: tcString ?? null, ...detail },
      });
    },
    [tcString, vendorListVersion],
  );

  const accept = () => {
    pushDataLayer('consent_accept_all', { purposes: ['1', '2', '3', '4'] });
    onAcceptAll();
  };

  const reject = () => {
    pushDataLayer('consent_reject_all', { purposes: [] });
    onRejectAll?.();
  };

  return (
    <aside
      role="dialog"
      aria-label="Consent preferences"
      className="meshant-consent-banner"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'var(--meshant-consent-bg, #111827)',
        color: 'var(--meshant-consent-fg, #f9fafb)',
        padding: '1rem 1.25rem',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.75rem',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 9999,
        fontFamily: 'system-ui, sans-serif',
        fontSize: '0.9rem',
      }}
    >
      <p style={{ margin: 0, flex: '1 1 280px', lineHeight: 1.5 }}>
        We use cookies and similar technologies per IAB Transparency &amp; Consent Framework v2.2. See our{' '}
        <a href={policyUrl} style={{ color: '#93c5fd' }}>
          privacy notice
        </a>
        .
      </p>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {onManagePreferences ? (
          <button
            type="button"
            className="meshant-consent-manage"
            onClick={onManagePreferences}
            style={btnSecondary}
          >
            Manage preferences
          </button>
        ) : null}
        {onRejectAll ? (
          <button type="button" className="meshant-consent-reject" onClick={reject} style={btnSecondary}>
            Reject non-essential
          </button>
        ) : null}
        <button type="button" className="meshant-consent-accept" onClick={accept} style={btnPrimary}>
          Accept all
        </button>
      </div>
    </aside>
  );
}

const btnPrimary: CSSProperties = {
  background: '#2563eb',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '0.5rem 1rem',
  cursor: 'pointer',
  fontWeight: 600,
};

const btnSecondary: CSSProperties = {
  ...btnPrimary,
  background: 'transparent',
  border: '1px solid #4b5563',
  color: '#e5e7eb',
};

export default ConsentBanner;
